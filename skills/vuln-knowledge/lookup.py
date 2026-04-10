#!/usr/bin/env python3
"""
vuln-knowledge lookup: BM25 search over the local corpus.

Usage:
    python3 lookup.py --query "ssrf to rce aws metadata" --mode auto --k 5
    python3 lookup.py --query "CVE-2024-3094" --k 3
    python3 lookup.py --rebuild-index

Output: JSON to stdout matching the schema in SKILL.md.
"""

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

# Resolve paths relative to this script so it works from any cwd
SKILL_DIR = Path(__file__).resolve().parent
CORPUS_DIR = SKILL_DIR.parent.parent / "corpus"
INDEX_PATH = SKILL_DIR / "index.db"
CACHE_DIR = CORPUS_DIR / "cache"

# Files we'll index. Markdown is the primary format; .yaml/.yml caught
# for nuclei templates which are structured-data-as-docs.
INDEXABLE_EXTS = {".md", ".markdown", ".txt", ".yaml", ".yml"}

# Skip these directories anywhere in the tree — they're noise
SKIP_DIRS = {".git", "node_modules", ".github", "images", "img", "assets"}

# Chunking: we split long files by heading so retrieval returns focused
# sections rather than whole files. Falls back to fixed-size chunks for
# files without headings.
MAX_CHUNK_CHARS = 2000
HEADING_RE = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)


def db_connect():
    conn = sqlite3.connect(INDEX_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_index():
    """Create the FTS5 virtual table. FTS5 ships with stock Python sqlite3."""
    conn = db_connect()
    conn.executescript("""
        DROP TABLE IF EXISTS chunks;
        CREATE VIRTUAL TABLE chunks USING fts5(
            source_path,
            source_repo,
            heading,
            content,
            tokenize = 'porter unicode61'
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    return conn


def chunk_file(path: Path) -> list[dict]:
    """Split a markdown file into heading-bounded chunks."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    if not text.strip():
        return []

    chunks = []
    headings = list(HEADING_RE.finditer(text))

    if not headings:
        # No headings — split by size
        for i in range(0, len(text), MAX_CHUNK_CHARS):
            chunks.append({
                "heading": path.stem,
                "content": text[i:i + MAX_CHUNK_CHARS].strip()
            })
        return chunks

    # Walk heading boundaries
    for i, h in enumerate(headings):
        start = h.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        section = text[start:end].strip()
        heading_line = h.group().lstrip("#").strip()

        # If the section is huge, sub-chunk it
        if len(section) <= MAX_CHUNK_CHARS:
            chunks.append({"heading": heading_line, "content": section})
        else:
            for j in range(0, len(section), MAX_CHUNK_CHARS):
                chunks.append({
                    "heading": heading_line,
                    "content": section[j:j + MAX_CHUNK_CHARS].strip()
                })
    return chunks


def build_index(verbose=False):
    """Walk corpus/, chunk every indexable file, insert into FTS5."""
    if not CORPUS_DIR.exists():
        print(f"ERROR: corpus directory not found: {CORPUS_DIR}", file=sys.stderr)
        sys.exit(1)

    conn = init_index()
    cur = conn.cursor()
    file_count = 0
    chunk_count = 0
    start = time.time()

    for repo_dir in sorted(CORPUS_DIR.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name == "cache":
            continue
        repo_name = repo_dir.name
        if verbose:
            print(f"  indexing {repo_name}/...", file=sys.stderr)

        for path in repo_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in INDEXABLE_EXTS:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue

            rel_path = str(path.relative_to(CORPUS_DIR))
            for chunk in chunk_file(path):
                cur.execute(
                    "INSERT INTO chunks (source_path, source_repo, heading, content) VALUES (?, ?, ?, ?)",
                    (rel_path, repo_name, chunk["heading"], chunk["content"])
                )
                chunk_count += 1
            file_count += 1

    cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("built_at", str(int(time.time()))))
    cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("file_count", str(file_count)))
    cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("chunk_count", str(chunk_count)))
    conn.commit()
    conn.close()

    elapsed = time.time() - start
    print(f"Indexed {file_count} files, {chunk_count} chunks in {elapsed:.1f}s",
          file=sys.stderr)


def sanitize_query(q: str) -> str:
    """
    FTS5 has its own query syntax. We want to allow natural language
    without users (or the LLM) having to escape special characters.
    Strategy: strip FTS operators, then OR-join the terms so any match counts.
    """
    # Remove FTS5 metacharacters
    cleaned = re.sub(r'[\"\(\)\*\:\^]', " ", q)
    # Collapse whitespace
    terms = [t for t in cleaned.split() if len(t) > 1]
    if not terms:
        return ""
    # CVE IDs and similar should match exactly
    quoted = []
    for t in terms:
        if re.match(r"^CVE-\d{4}-\d+$", t, re.IGNORECASE):
            quoted.append(f'"{t}"')
        else:
            quoted.append(t)
    return " OR ".join(quoted)


def search(query: str, k: int = 5) -> list[dict]:
    if not INDEX_PATH.exists():
        print("ERROR: index not built. Run with --rebuild-index", file=sys.stderr)
        sys.exit(1)

    fts_query = sanitize_query(query)
    if not fts_query:
        return []

    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT source_path, source_repo, heading, content,
                   bm25(chunks) AS score
            FROM chunks
            WHERE chunks MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (fts_query, k)
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(f"ERROR: query failed: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()

    # bm25() returns lower=better; normalize to 0-1 relevance for the schema
    if not rows:
        return []
    raw_scores = [r["score"] for r in rows]
    min_s, max_s = min(raw_scores), max(raw_scores)
    spread = (max_s - min_s) or 1.0

    results = []
    for r in rows:
        relevance = 1.0 - ((r["score"] - min_s) / spread)
        results.append({
            "source": r["source_path"],
            "source_type": "local",
            "title": r["heading"],
            "content": r["content"],
            "relevance": round(relevance, 3),
            "url": None,
            "repo": r["source_repo"],
        })
    return results


def confidence(results: list[dict]) -> float:
    """Crude confidence: top-result relevance, dampened by result count."""
    if not results:
        return 0.0
    top = results[0]["relevance"]
    count_factor = min(len(results) / 5.0, 1.0)
    return round(top * 0.7 + count_factor * 0.3, 3)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--query", help="Search query")
    p.add_argument("--mode", default="auto",
                   choices=["auto", "lookup", "exploit", "remediate"])
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--rebuild-index", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if args.rebuild_index:
        build_index(verbose=args.verbose)
        return

    if not args.query:
        p.error("--query is required unless --rebuild-index")

    results = search(args.query, k=args.k)
    output = {
        "query": args.query,
        "mode": args.mode,
        "results": results,
        "confidence": confidence(results),
        "fetched_external": False,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()