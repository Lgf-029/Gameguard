import pymysql
from app.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

class MySQLClient:
    def __init__(self):
        self.conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            autocommit=True,
        )

    def execute_query(self, sql: str, params: tuple = None) -> list[dict]:
        """执行查询，返回字典列表"""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def execute_insert(self, sql: str, params: tuple = None) -> int:
        """单行插入，返回自增ID"""
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.lastrowid

    def execute_insert_many(self, sql: str, params_list: list[tuple]) -> int:
        """批量插入，返回影响行数"""
        with self.conn.cursor() as cursor:
            return cursor.executemany(sql, params_list)

    def execute_update(self, sql: str, params: tuple = None) -> int:
        """执行更新/删除，返回影响行数"""
        with self.conn.cursor() as cursor:
            affected = cursor.execute(sql, params)
            return affected

    def close(self):
        self.conn.close()