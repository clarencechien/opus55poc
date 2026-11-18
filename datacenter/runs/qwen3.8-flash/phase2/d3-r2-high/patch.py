p = "final.py"
s = open(p).read()
s = s.replace("lb = sum(abs(TER[rid][i]-TER[rid][1][i]) for i in range(3))",
              "lb = sum(abs(TER[rid][0][i]-TER[rid][1][i]) for i in range(3))")
open(p, "w").write(s)
print("patched")
