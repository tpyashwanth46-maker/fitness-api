import psycopg2

conn = psycopg2.connect(
    dbname="fitness_db",
    user="postgres",
    password="yash",
    host="localhost",
    port="5432"
)

print("Connected successfully!")

conn.close()