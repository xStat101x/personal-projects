#update

This is the location for creating update requests for the design of the [[PLAN]] or [[SYSTEM_PROMPT]] to improve as I see fit. I have added links to each section that needs updated. Feel free to update anything else within these files that you think are necessary based on the information i provided in this file. Make sure to audit your choices and make sure that they are beneficial to the development of this AI agent. Also ask question if you need clarification don't assume you understand everything i envision about this AI as you don't have all the information and questions are healthy for the continued development process.

### [[PLAN]]
^d320aa
1. Update to allow 0-day exploits discovering but create strict permissions so that this isn't sole focus. Maybe add a 10 attempt move on system so it doesn't loop. Also needs a very high confidence interval to attempt actions. ^943196
2. These are skills not agents. Review openclaw file structure as building new agents should be done in the /agents folder. Make sure we implement both skills and agents to be leveraged. ^fccf40
3. Make sure to separate different tasks into separate agents with their own specific skills as to not overload the context of one agent. ^03b9ef
4. No DoS or DDoS ever is allowed  ^88e7b8
5. Expand upon this section its going to be crucial for development and fine toning. It is also important to allow operator intervention on improvements. A way to read it before it gets updated would be helpful. A separate file with update request before writing to main file.  ^e04587
6. Make sure to not that this agent runs inside a kali linux virtual machine it will have all the default tooling of a kali VM so adjust the list accordingly.^149958
7. Report writing should happen at the end after gathering info from network cloud and stretch milestones. It isn't a bad idea to also implement it throughout in case it gets stuck at a certain spot but ill let you decide if that is necessary or just a waste of resources. ^acd671

# [[PLAN#^3e7ada| Question Answers]]
1. No need to spin them up I will connect them manually before use if that is the target we are facing.
2. Adjusted severity based on business context primarily as well as CVSS 3.1/4.0 in a more technical report.
3. Give it full autonomous. I will test it and make adjustments after it runs by itself. The first targets will be local VMs anyways (Don't include in PLAN) so it shouldn't need babysitting as it can't break anything serious.
4. No repo refresh that is there for version control as I update it myself. I will update knowledge base manually for the time being until it is working as intended then i will automate it further by having it update its own knowledge through git.
5. Whatever you think is best for context management and effectiveness. I am not sure about the pros/cons of single vs multiple sandboxes
6. I am not entirely knowledgable on the Mythos project but my understanding it is really good at code analysis which makes it an extremely powerful offensive security tool. I want to create this so that I am capable of finding vulnerabilities that human testers would miss at speeds humans can't keep up with. 

# [[SYSTEM_PROMPT]]
1. I think adding a subfolder in corpus or separate from corpus that is personal knowledge rather than vulnerability information and hacking tricks from online. Maybe also organizing the current knowledge structure would be a good idea too. ^bc912c
2. Make sure to specify a non technical and technical report ^327737

# Questions for AI Development Assistant
1. What other skills will be necessary to implement for maximum effectiveness?
2. Can we create a CTF development level as a flag so that I can prompt the AI for less restrictions allowing target destruction with the exception of DoS and DDoS. This would be used when faced with boxes like hack the box or try hack me so allowing it to do what you would believe as necessary for those type of boxes would allow for faster development and improvement before attacking live targets.
3. Can we make sure to adjust the plan to match the OpenClaw file structure so that when we implement this it doesn't compromise the structure and create headaches for development?
4. Can we also implement a development mode or flag that creates extra logging including usage every command executed and reasoning for attack paths as they are being executed? Outputted either live or to a file whichever you think is best.
5. Do you think this agent set up would work temporally on free models as I don't want to spend to much capital on development. If not that is ok don't change anything I just need to know so i can plan for the situation.
6. Review the PLAN and SYSTEM_PROMPT and check if there is any inconsistency or if we missed anything that would increase the effectiveness of the AI based on the context and concerns brought up in the Design Updates file.