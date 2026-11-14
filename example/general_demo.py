# 通用 Python 模式示例：成绩统计 + 最大公约数
# 直接运行: python general_demo.py
# 转成 Scratch: python converter.py py2scratch example/general_demo.py example/general_demo.sb3 --mode general

scores = [88, 92, 75, 60, 95]

total = 0
passed = 0
for score in scores:
    total += score
    if score >= 60:
        passed += 1

average = total / len(scores)
print("总分", total)
print("平均分", average)
print("及格人数", passed)


def gcd(x, y):
    a = x
    b = y
    while b != 0:
        t = b
        b = a % b
        a = t
    return a


print("gcd(48, 18) =", gcd(48, 18))
