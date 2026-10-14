#!/usr/bin/python
import sys

def main():
    num = 12645638
    num = ~num
    num = num ^ 12648430
    num = ~num
    num = num >> 2
    print(num)

if __name__ == '__main__':
    main()