import logging
import mysql.connector
from fastapi import Form, HTTPException, Request, Body
from pydantic import BaseModel, Field
from mysql.connector import Error
from config import Config

logger = logging.getLogger(__name__)

class DatabaseQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)

class DatabaseExecuteRequest(BaseModel):
    query: str

def get_db_connection():
    """创建MySQL数据库连接"""
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset='utf8mb4',
            connect_timeout=5
        )
        return connection
    except Exception as e:
        logger.error(f"MySQL connection failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )

def preprocess_sql_query(query: str) -> str:
    """预处理SQL查询"""
    query = query.replace('```sql', '').replace('```', '')
    lines = [line.strip() for line in query.split('\n\n') if line.strip()]
    return lines[-1] if lines else ''

async def query_data(
    request: Request,
    query: str = Form(None),
    db_request: DatabaseQueryRequest = Body(None)
):
    """执行查询操作"""
    # 参数处理
    if query is not None:
        db_request = DatabaseQueryRequest(query=query)
    elif db_request is None:
        raise HTTPException(status_code=422, detail="Missing request body")
    
    if not db_request.query.strip():
        raise HTTPException(status_code=422, detail="Query parameter is required")
    
    # 查询预处理
    sql_query = db_request.query
    if Config.QUERY_CLEANING:
        sql_query = preprocess_sql_query(sql_query)
    
    # 执行查询
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql_query)
        result = cursor.fetchall()
        return result
    except Error as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

async def execute_query(request: DatabaseExecuteRequest):
    """执行更新操作"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(request.query)
        connection.commit()
        return cursor.rowcount
    except Error as e:
        logger.error(f"Database execute failed: {e}")
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()