import csv
from psycopg2 import connect, extensions, sql

filepath = None

def connect_db(host="localhost", username="otterservice", password="mypass"):
    conn = connect(dbname='otter_db',
               user=username,
               host=host,
               password=password)
    conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    return conn

def main():
    global filepath
    with open(filepath, newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        conn = connect_db()
        cursor = conn.cursor()
        for row in spamreader:
            username, password = row[:2]
            if username.lower() == "username":
                # skip heading
                continue
            insert_command = """
                INSERT INTO users (username, password) VALUES (\'{}\', \'{}\')
                ON CONFLICT (username)
                DO UPDATE SET password = \'{}\'
                """.format(username, password, password)
            cursor.execute(insert_command)
            
if __name__ == "__main__":
    if filepath is None:
        filepath = input("Enter the path to the users csv file: ")
    main()