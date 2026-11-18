import re
s=open('build1.py').read()
s=s.replace("                    it[0]=it[1]-800; it[2]=True","                    it[1]=it[1]+200.; it[2]=True")
open('build1.py','w').write(s)
print("patched" if "it[1]+200" in s else "FAIL")
