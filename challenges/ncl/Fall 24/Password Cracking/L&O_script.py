#!/usr/bin/python


import requests


from bs4 import BeautifulSoup

page = requests.get("https://en.wikipedia.org/wiki/List_of_Law_%26_Order:_Special_Victims_Unit_episodes_(seasons_1%E2%80%9319)#Season_1_(1999%E2%80%932000)")

print(page.status_code)

soup = BeautifulSoup(page.content, 'html.parser')

object = soup.find(id="mw-content-text")

episodes = object.find_all(class_="summary")
out = episodes[0]
print(out.string)

f= open("L&O_wordlist2.txt", "w")

for x in episodes:
    for string in x.strings:
        if (string == ""):
            continue
        elif (string == "\""):
            continue
        elif (string[0] == '"'): 
            fixed_string = string[1:-1]
            f.write(fixed_string + "\n")
            
            for num in range(100):
                if num < 10:
                    f.write(fixed_string + "0" + str(num) + "\n")
                else:
                    f.write(fixed_string + str(num) + "\n")
            
        else:
            f.write(string + "\n")
            
            for num in range(100):
                if num < 10:
                    f.write(string + "0" + str(num) + "\n")
                else:
                    f.write(string + str(num) + "\n")
            
            
    
    
        
