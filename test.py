from collections import deque

q = deque([(1, 2, 3)])

q.append((3, 4, 5))

print(q)
print(q.popleft())
print(q)