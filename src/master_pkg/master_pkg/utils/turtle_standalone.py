import csv
import turtle

#Nastavení
CSV_FILE = "output.csv"     
SCALE = 3                  
X_OFFSET = 0           
Y_OFFSET = -100            

#Inicializace turtle
t = turtle.Turtle()
wn = turtle.Screen()
wn.bgcolor("white")        
t.color("black")           
t.pensize(2)               
t.speed(0)
t.hideturtle()
t.penup()

#Načtení bodů
points = []
with open(CSV_FILE, "r") as f:
    reader = csv.reader(f)
    for row in reader:
        x, y, z = map(float, row)
        points.append((x, y, z))

#Vykreslování dráhy
for x, y, z in points:
    screen_x = x * SCALE + X_OFFSET
    screen_y = y * SCALE + Y_OFFSET
    if z > 0:  # pero nahoře
        t.penup()
    else:      # kreslí
        t.pendown()
    t.goto(screen_x, screen_y)

turtle.done()
