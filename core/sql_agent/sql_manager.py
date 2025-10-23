import os
import sqlite3
import logging
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from config import Config

logger = logging.getLogger(__name__)

class SQLDatabaseManager:
    """SQL数据库管理器 (MySQL)"""

    def __init__(self):
        self.default_database = Config.SQL_DB_DATABASE
        self._test_connection()

    def get_database_connection(self, db_name: str = None) -> str:
        """获取MySQL数据库连接字符串"""
        if db_name is None:
            db_name = self.default_database

        if Config.SQL_DB_TYPE.lower() == "mysql":
            return f"mysql+mysqlconnector://{Config.SQL_DB_USERNAME}:{Config.SQL_DB_PASSWORD}@{Config.SQL_DB_HOST}:{Config.SQL_DB_PORT}/{db_name}"
        else:
            raise ValueError(f"Unsupported database type: {Config.SQL_DB_TYPE}. Only MySQL is supported in this configuration.")

    def _test_connection(self):
        """测试MySQL连接"""
        try:
            connection_string = self.get_database_connection()
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("MySQL connection test successful")
        except Exception as e:
            logger.error(f"MySQL connection test failed: {e}")

    def create_sample_tables(self):
        """在现有MySQL数据库中创建示例表"""
        try:
            connection_string = self.get_database_connection()
            engine = create_engine(connection_string)

            with engine.connect() as conn:
                # 检查数据库是否存在，不存在则创建
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {self.default_database}"))
                conn.execute(text(f"USE {self.default_database}"))

                # 创建产品表
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS products (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        category VARCHAR(50),
                        price DECIMAL(10,2),
                        stock INT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """))

                # 创建订单表
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        product_id INT,
                        quantity INT,
                        order_date DATE,
                        customer_name VARCHAR(100),
                        total_amount DECIMAL(10,2),
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """))

                # 插入示例数据
                conn.execute(text("""
                    INSERT IGNORE INTO products (id, name, category, price, stock) VALUES
                    (1, 'iPhone 15', 'Electronics', 999.99, 100),
                    (2, 'MacBook Pro', 'Electronics', 1999.99, 50),
                    (3, 'Coffee Maker', 'Appliances', 89.99, 200),
                    (4, 'Office Chair', 'Furniture', 299.99, 75)
                """))

                conn.execute(text("""
                    INSERT IGNORE INTO orders (id, product_id, quantity, order_date, customer_name, total_amount, status) VALUES
                    (1, 1, 2, '2024-01-15', 'Alice Johnson', 1999.98, 'completed'),
                    (2, 2, 1, '2024-01-16', 'Bob Smith', 1999.99, 'completed'),
                    (3, 1, 1, '2024-01-17', 'Charlie Brown', 999.99, 'pending'),
                    (4, 3, 3, '2024-01-18', 'David Wilson', 269.97, 'completed')
                """))

                conn.commit()

            logger.info("Simplified MySQL tables created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create sample MySQL tables: {e}")
            return False

    def get_database_schema(self, db_name: str = None) -> str:
        """获取MySQL数据库模式"""
        try:
            if db_name is None:
                db_name = self.default_database

            connection_string = self.get_database_connection(db_name)
            engine = create_engine(connection_string)

            with engine.connect() as conn:
                # 获取所有表
                tables_result = conn.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """), (db_name,))

                tables = [row[0] for row in tables_result]
                schema_info = []

                for table in tables:
                    schema_info.append(f"Table: {table}")

                    # 获取表的列信息
                    columns_result = conn.execute(text("""
                        SELECT
                            column_name,
                            data_type,
                            is_nullable,
                            column_default,
                            column_key
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                    """), (db_name, table))

                    for column_row in columns_result:
                        column_name, data_type, is_nullable, column_default, column_key = column_row
                        nullable_info = "NULL" if is_nullable == "YES" else "NOT NULL"
                        key_info = f" ({column_key})" if column_key else ""
                        default_info = f" DEFAULT {column_default}" if column_default else ""

                        schema_info.append(f"  - {column_name} ({data_type}) {nullable_info}{key_info}{default_info}")

                    schema_info.append("")  # 表之间的空行

                return "\n".join(schema_info).strip() if schema_info else f"No tables found in database '{db_name}'"

        except Exception as e:
            logger.error(f"Failed to get database schema: {e}")
            return f"Error retrieving database schema: {str(e)}"

    def execute_query(self, query: str, db_name: str = None) -> Dict[str, Any]:
        """安全执行SQL查询"""
        try:
            if db_name is None:
                db_name = self.default_database

            connection_string = self.get_database_connection(db_name)
            engine = create_engine(connection_string)

            with engine.connect() as conn:
                # 安全检查：只允许SELECT查询
                query_upper = query.strip().upper()
                if not query_upper.startswith('SELECT'):
                    raise ValueError("Only SELECT queries are allowed for security reasons")

                result = conn.execute(text(query))

                # 处理查询结果
                if result.returns_rows:
                    rows = result.fetchall()
                    columns = result.keys()

                    # 格式化结果为表格形式
                    formatted_result = []
                    if rows:
                        # 添加表头
                        formatted_result.append(" | ".join(columns))
                        formatted_result.append("-" * len(" | ".join(columns)))

                        # 添加数据行
                        for row in rows:
                            formatted_result.append(" | ".join(str(cell) for cell in row))

                        return {
                            "success": True,
                            "data": rows,
                            "columns": columns,
                            "formatted": "\n".join(formatted_result),
                            "row_count": len(rows)
                        }
                    else:
                        return {
                            "success": True,
                            "data": [],
                            "columns": columns,
                            "formatted": "Query executed successfully, but no data returned.",
                            "row_count": 0
                        }
                else:
                    return {
                        "success": True,
                        "message": "Query executed successfully.",
                        "row_count": result.rowcount if hasattr(result, 'rowcount') else 0
                    }

        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            return {
                "success": False,
                "error": str(e),
                "formatted": f"Error executing query: {str(e)}"
            }

# 全局实例
sql_db_manager = SQLDatabaseManager()

# 初始化示例数据（在服务启动时调用）
def initialize_sql_data():
    """初始化SQL示例数据"""
    try:
        sql_db_manager.create_sample_tables()
        logger.info("SQL sample data initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize SQL sample data: {e}")