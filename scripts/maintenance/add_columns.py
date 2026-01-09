#!/usr/bin/env python3
import sqlite3

def add_hprim_columns():
    conn = sqlite3.connect('data/db.sqlite3')
    cursor = conn.cursor()

    # Check existing columns - try different table name variations
    table_names = ['systemendpoint', 'SystemEndpoint', 'systemEndpoint']
    columns = []
    
    for table_name in table_names:
        try:
            cursor.execute(f'PRAGMA table_info({table_name})')
            columns = [row[1] for row in cursor.fetchall()]
            if columns:
                print(f'Found table: {table_name}')
                break
        except:
            continue
    
    if not columns:
        print('Table not found')
        conn.close()
        return

    # Add missing columns
    columns_to_add = [
        ('emit_hprim_ccam', f'ALTER TABLE {table_name} ADD COLUMN emit_hprim_ccam INTEGER DEFAULT 0'),
        ('emit_hprim_ngap', f'ALTER TABLE {table_name} ADD COLUMN emit_hprim_ngap INTEGER DEFAULT 0'),
        ('emit_hprim_ucd', f'ALTER TABLE {table_name} ADD COLUMN emit_hprim_ucd INTEGER DEFAULT 0'),
        ('emit_hprim_lpp', f'ALTER TABLE {table_name} ADD COLUMN emit_hprim_lpp INTEGER DEFAULT 0'),
    ]

    for col_name, sql in columns_to_add:
        if col_name not in columns:
            cursor.execute(sql)
            print(f'Added {col_name}')
        else:
            print(f'{col_name} already exists')

    conn.commit()
    conn.close()
    print('Done')

if __name__ == '__main__':
    add_hprim_columns()