from fastapi import Form, HTTPException, Request, Body
from pydantic import BaseModel, Field
import mysql.connector
from mysql.connector import Error
import time
import logging
from config import Config

logger = logging.getLogger(__name__)

class DatabaseQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="SQL query string (required)")

class DatabaseExecuteRequest(BaseModel):
    query: str

def get_db_connection():
    """创建并返回MySQL数据库连接"""
    # 打印连接配置
    logger.info(f"DBSETTING： - host:{Config.MYSQL_HOST} port:{Config.MYSQL_PORT} "
               f"user:{Config.MYSQL_USER} db:{Config.MYSQL_DATABASE}")
    
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            try:
                connection = mysql.connector.connect(
                    host=Config.MYSQL_HOST,
                    port=Config.MYSQL_PORT,
                    user=Config.MYSQL_USER,
                    password=Config.MYSQL_PASSWORD,
                    database=Config.MYSQL_DATABASE,
                    connect_timeout=5
                )
            except Exception as e:
                logger.error(f"MySQL connection failed with config: "
                           f"host={Config.MYSQL_HOST}, "
                           f"port={Config.MYSQL_PORT}, "
                           f"user={Config.MYSQL_USER}, "
                           f"database={Config.MYSQL_DATABASE}")
                raise
            logger.info("Successfully connected to MySQL database")
            return connection
        except Error as e:
            logger.error(f"Attempt {attempt + 1} failed to connect to MySQL: {e}")
            if attempt == max_retries - 1:
                logger.error("All connection attempts failed")
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Database connection failed",
                        "message": "Could not establish database connection",
                        "solution": "Check database service and credentials",
                        "config": {
                            "host": Config.MYSQL_HOST,
                            "port": Config.MYSQL_PORT,
                            "database": Config.MYSQL_DATABASE
                        }
                    }
                )
            time.sleep(retry_delay)

def preprocess_sql_query(query: str) -> str:
    """预处理SQL查询字符串
    1. 处理多换行，获取最后一个非空内容
    2. 去除代码块标记(```sql和```)
    3. 去除前后空格
    """
    # 去除代码块标记
    query = query.replace('```sql', '').replace('```', '')
    
    # 分割并获取最后一个非空内容
    lines = [line.strip() for line in query.split('\n\n') if line.strip()]
    if not lines:
        return ''
    
    return lines[-1]

async def query_data(
    request: Request,
    query: str = Form(None),
    db_request: DatabaseQueryRequest = Body(None)
):
    # 处理form-data格式请求
    if query is not None:
        db_request = DatabaseQueryRequest(query=query)
    # 处理json格式请求
    elif db_request is None:
        raise HTTPException(
            status_code=422,
            detail={"error": "Missing request body"}
        )
    
    # 验证查询参数
    if not db_request.query or not db_request.query.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Missing required parameter",
                "message": "The 'query' parameter is required and cannot be empty",
                "solution": "Provide a valid SQL query in the request body"
            }
        )
    
    # 如果配置开启查询清洗，则执行预处理
    query = db_request.query
    if Config.QUERY_CLEANING:
        query = preprocess_sql_query(query)
    
    """执行查询并返回结果
    WARNING: 不使用参数化查询，存在SQL注入风险
    
    请求示例:
    {
        "query": "SELECT * FROM users WHERE id = 1"
    }

    返回格式:
    [
        {
            "column1": "value1",
            "column2": "value2",
            ...
        },
        ...
    ]
    或空列表 []
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except Error as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

async def execute_query(request: DatabaseExecuteRequest):
    """执行插入/更新/删除操作
    WARNING: 不使用参数化查询，存在SQL注入风险
    
    请求示例:
    {
        "query": "INSERT INTO users (name) VALUES ('John')"
    }
    """
    query = request.query
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
        return cursor.rowcount
    except Error as e:
        logger.error(f"Database execute failed: {e}")
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
