from psycopg2 import connect, extensions, sql

conn = connect(dbname='postgres',
               user='admin',
               host='',
               password='')

conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()
cursor.execute('CREATE DATABASE otter_db')
cursor.close()
conn.close()

conn = connect(dbname='otter_db',
               user='admin',
               host='',
               password='')

conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

queries = [
    '''
    CREATE TABLE users (
        username TEXT PRIMARY KEY,
        password CHAR(20),
        api_key CHAR(20),
        email TEXT
    )
    ''',
    '''
    CREATE TABLE classes (
        class_id SERIAL PRIMARY KEY,
        class_name TEXT
    )
    ''',
    '''
    CREATE TABLE assignments (
        assignment_id SERIAL PRIMARY KEY,
        class_id INTEGER REFERENCES classes (class_id),
        assignment_name TEXT
    )
    ''',
    '''
    CREATE TABLE submissions (
        submission_id SERIAL PRIMARY KEY,
        assignment_id INTEGER REFERENCES assignments(assignment_id),
        file_path TEXT,
        timestamp TIMESTAMPTZ,
        score JSONB
    )
    '''
]

for query in queries:
    cursor.execute(query)
    
cursor.close()
conn.close()
