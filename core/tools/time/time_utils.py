import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import re
import calendar

logger = logging.getLogger(__name__)

class TimeUtils:
    """时间相关工具类，支持自然语言时间解析和SQL时间条件生成"""

    # 时间表达式映射
    TIME_EXPRESSIONS = {
        # 绝对时间
        '今天': 'today',
        '今日': 'today',
        '昨天': 'yesterday',
        '昨日': 'yesterday',
        '明天': 'tomorrow',
        '明日': 'tomorrow',
        '前天': 'day_before_yesterday',
        '后天': 'day_after_tomorrow',

        # 相对月份
        '本月': 'current_month',
        '这个月': 'current_month',
        '当月': 'current_month',
        '上月': 'last_month',
        '上个月': 'last_month',
        '上月': 'last_month',
        '下月': 'next_month',
        '下个月': 'next_month',

        # 相对年份
        '本年': 'current_year',
        '今年': 'current_year',
        '当年': 'current_year',
        '去年': 'last_year',
        '上年': 'last_year',
        '明年': 'next_year',

        # 相对季度
        '本季度': 'current_quarter',
        '这个季度': 'current_quarter',
        '当季度': 'current_quarter',
        '上季度': 'last_quarter',
        '下季度': 'next_quarter',

        # 相对周
        '本周': 'current_week',
        '这周': 'current_week',
        '上周': 'last_week',
        '上个星期': 'last_week',
        '下周': 'next_week',
        '下个星期': 'next_week',

        # 模糊时间天数
        r'最近(\d+)[天日]': 'last_days',
        r'过去(\d+)[天日]': 'last_days',
        r'前(\d+)[天日]': 'last_days',
        r'未来(\d+)[天日]': 'next_days',
        r'后(\d+)[天日]': 'next_days',
        r'接下来(\d+)[天日]': 'next_days',

        # 模糊时间年数
        r'最近(\d+)[年]': 'last_years',
        r'过去(\d+)[年]': 'last_years',
        r'前(\d+)[年]': 'last_years',
        r'近(\d+)[年]': 'last_years',
        r'最近([一二三四五六七八九十百千万两]+)[年]': 'last_years',
        r'过去([一二三四五六七八九十百千万两]+)[年]': 'last_years',
        r'前([一二三四五六七八九十百千万两]+)[年]': 'last_years',
        r'近([一二三四五六七八九十百千万两]+)[年]': 'last_years',

        # 模糊时间月数
        r'最近(\d+)[个]?[月]': 'last_months',
        r'过去(\d+)[个]?[月]': 'last_months',
        r'前(\d+)[个]?[月]': 'last_months',
        r'近(\d+)[个]?[月]': 'last_months',
        r'最近([一二三四五六七八九十百千万两]+)[个]?[月]': 'last_months',
        r'过去([一二三四五六七八九十百千万两]+)[个]?[月]': 'last_months',
        r'前([一二三四五六七八九十百千万两]+)[个]?[月]': 'last_months',
        r'近([一二三四五六七八九十百千万两]+)[个]?[月]': 'last_months',
    }

    @staticmethod
    def _chinese_number_to_int(chinese_num: str) -> int:
        """将中文数字转换为阿拉伯数字"""
        chinese_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '两': 2, '百': 100, '千': 1000, '万': 10000
        }

        result = 0
        temp = 0

        for char in chinese_num:
            if char in chinese_map:
                num = chinese_map[char]
                if num == 10 or num == 100 or num == 1000 or num == 10000:
                    # 十、百、千、万是位数
                    if temp == 0:
                        temp = 1
                    result += temp * num
                    temp = 0
                else:
                    temp = temp * 10 + num if temp > 0 else num

        result += temp
        return result if result > 0 else 1

    @staticmethod
    def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> Dict[str, Any]:
        """获取当前时间信息"""
        try:
            now = datetime.now()
            return {
                "success": True,
                "current_time": now.strftime(format),
                "timestamp": now.timestamp(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second,
                "weekday": now.weekday(),  # 0=Monday, 6=Sunday
                "weekday_name": now.strftime("%A"),
                "month_name": now.strftime("%B")
            }
        except Exception as e:
            logger.error(f"Get current time failed: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def parse_time_expression(expression: str, base_date: str = "") -> Dict[str, Any]:
        """解析时间表达式为具体时间范围

        Args:
            expression: 时间表达式，如'本月'、'最近7天'、'2024年1月'等
            base_date: 基准日期，格式为YYYY-MM-DD，默认为当前日期

        Returns:
            包含时间范围信息的字典
        """
        try:
            if not base_date:
                base_date = datetime.now()
            else:
                base_date = datetime.strptime(base_date, "%Y-%m-%d")

            expression = expression.strip()

            # 检查预定义时间表达式
            for pattern, time_type in TimeUtils.TIME_EXPRESSIONS.items():
                if re.fullmatch(pattern, expression):
                    return TimeUtils._calculate_time_range(time_type, expression, base_date)

            # 检查绝对时间表达式（如：2024年1月、2024年、1月）
            absolute_result = TimeUtils._parse_absolute_time(expression, base_date)
            if absolute_result:
                return absolute_result

            # 如果都不匹配，返回错误
            return {
                "success": False,
                "error": f"无法识别的时间表达式: {expression}",
                "expression": expression
            }

        except Exception as e:
            logger.error(f"Time expression parsing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "expression": expression
            }

    @staticmethod
    def _calculate_time_range(time_type: str, expression: str, base_date: datetime) -> Dict[str, Any]:
        """计算具体时间范围"""
        try:
            if time_type == 'today':
                start_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = base_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'yesterday':
                yesterday = base_date - timedelta(days=1)
                start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'tomorrow':
                tomorrow = base_date + timedelta(days=1)
                start_date = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'day_before_yesterday':
                target_date = base_date - timedelta(days=2)
                start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'day_after_tomorrow':
                target_date = base_date + timedelta(days=2)
                start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'current_month':
                start_date = base_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_day = calendar.monthrange(base_date.year, base_date.month)[1]
                end_date = base_date.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'last_month':
                if base_date.month == 1:
                    # 去年12月
                    start_date = base_date.replace(year=base_date.year-1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
                    last_day = calendar.monthrange(base_date.year-1, 12)[1]
                    end_date = base_date.replace(year=base_date.year-1, month=12, day=last_day, hour=23, minute=59, second=59, microsecond=999999)
                else:
                    # 同年上月
                    start_date = base_date.replace(month=base_date.month-1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    last_day = calendar.monthrange(base_date.year, base_date.month-1)[1]
                    end_date = base_date.replace(month=base_date.month-1, day=last_day, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'next_month':
                if base_date.month == 12:
                    # 明年1月
                    start_date = base_date.replace(year=base_date.year+1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    end_date = base_date.replace(year=base_date.year+1, month=1, day=31, hour=23, minute=59, second=59, microsecond=999999)
                else:
                    # 同年下月
                    start_date = base_date.replace(month=base_date.month+1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    last_day = calendar.monthrange(base_date.year, base_date.month+1)[1]
                    end_date = base_date.replace(month=base_date.month+1, day=last_day, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'current_year':
                start_date = base_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = base_date.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'last_year':
                start_date = base_date.replace(year=base_date.year-1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = base_date.replace(year=base_date.year-1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'next_year':
                start_date = base_date.replace(year=base_date.year+1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = base_date.replace(year=base_date.year+1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'current_quarter':
                quarter = (base_date.month - 1) // 3 + 1
                start_month = (quarter - 1) * 3 + 1
                start_date = base_date.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_month = start_month + 2
                last_day = calendar.monthrange(base_date.year, end_month)[1]
                end_date = base_date.replace(month=end_month, day=last_day, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'last_quarter':
                current_quarter = (base_date.month - 1) // 3 + 1
                if current_quarter == 1:
                    # 去年第4季度
                    start_month = 10
                    end_month = 12
                    year = base_date.year - 1
                else:
                    # 今年上季度
                    start_month = (current_quarter - 2) * 3 + 1
                    end_month = start_month + 2
                    year = base_date.year

                start_date = base_date.replace(year=year, month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
                last_day = calendar.monthrange(year, end_month)[1]
                end_date = base_date.replace(year=year, month=end_month, day=last_day, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'next_quarter':
                current_quarter = (base_date.month - 1) // 3 + 1
                if current_quarter == 4:
                    # 明年第1季度
                    start_month = 1
                    end_month = 3
                    year = base_date.year + 1
                else:
                    # 今年下季度
                    start_month = (current_quarter) * 3 + 1
                    end_month = start_month + 2
                    year = base_date.year

                start_date = base_date.replace(year=year, month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
                last_day = calendar.monthrange(year, end_month)[1]
                end_date = base_date.replace(year=year, month=end_month, day=last_day, hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'current_week':
                # 获取本周一
                days_since_monday = base_date.weekday()
                monday = base_date - timedelta(days=days_since_monday)
                start_date = monday.replace(hour=0, minute=0, second=0, microsecond=0)
                sunday = monday + timedelta(days=6)
                end_date = sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'last_week':
                # 获取上周一
                days_since_monday = base_date.weekday()
                last_monday = base_date - timedelta(days=days_since_monday + 7)
                start_date = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                last_sunday = last_monday + timedelta(days=6)
                end_date = last_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'next_week':
                # 获取下周一
                days_since_monday = base_date.weekday()
                next_monday = base_date - timedelta(days=days_since_monday - 7)
                start_date = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                next_sunday = next_monday + timedelta(days=6)
                end_date = next_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'last_days':
                # 解析天数
                match = re.search(r'(\d+)', expression)
                days = int(match.group(1))
                start_date = (base_date - timedelta(days=days-1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = base_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'next_days':
                # 解析天数
                match = re.search(r'(\d+)', expression)
                days = int(match.group(1))
                start_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = (base_date + timedelta(days=days-1)).replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'last_years':
                # 解析年数（支持阿拉伯数字和中文数字）
                # 先尝试阿拉伯数字
                match = re.search(r'(\d+)', expression)
                if match:
                    years = int(match.group(1))
                else:
                    # 尝试中文数字
                    chinese_num = re.search(r'([一二三四五六七八九十百千万两]+)', expression)
                    if chinese_num:
                        years = TimeUtils._chinese_number_to_int(chinese_num.group(1))
                    else:
                        years = 1  # 默认1年

                # 计算开始日期：N年前的今天
                start_date = (base_date - timedelta(days=years*365)).replace(hour=0, minute=0, second=0, microsecond=0)
                # 结束日期：昨天的结束时间
                end_date = (base_date - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)

            elif time_type == 'last_months':
                # 解析月数（支持阿拉伯数字和中文数字）
                # 先尝试阿拉伯数字
                match = re.search(r'(\d+)', expression)
                if match:
                    months = int(match.group(1))
                else:
                    # 尝试中文数字
                    chinese_num = re.search(r'([一二三四五六七八九十百千万两]+)', expression)
                    if chinese_num:
                        months = TimeUtils._chinese_number_to_int(chinese_num.group(1))
                    else:
                        months = 1  # 默认1个月

                # 计算开始日期：N个月前
                # 通过减去月份来计算，考虑年份变化
                target_month = base_date.month - months
                target_year = base_date.year

                while target_month <= 0:
                    target_month += 12
                    target_year -= 1

                start_date = base_date.replace(year=target_year, month=target_month, day=1, hour=0, minute=0, second=0, microsecond=0)
                # 结束日期：上个月的最后一天
                if base_date.month == 1:
                    end_month = 12
                    end_year = base_date.year - 1
                else:
                    end_month = base_date.month - 1
                    end_year = base_date.year

                last_day = calendar.monthrange(end_year, end_month)[1]
                end_date = base_date.replace(year=end_year, month=end_month, day=last_day, hour=23, minute=59, second=59, microsecond=999999)

            else:
                # 默认返回今天
                start_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = base_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            return {
                "success": True,
                "expression": expression,
                "time_type": time_type,
                "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "start_date_only": start_date.strftime("%Y-%m-%d"),
                "end_date_only": end_date.strftime("%Y-%m-%d"),
                "days_diff": (end_date.date() - start_date.date()).days + 1,
                "base_date": base_date.strftime("%Y-%m-%d")
            }

        except Exception as e:
            logger.error(f"Time range calculation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "expression": expression,
                "time_type": time_type
            }

    @staticmethod
    def _parse_absolute_time(expression: str, base_date: datetime) -> Optional[Dict[str, Any]]:
        """解析绝对时间表达式"""
        try:
            # 匹配年份：2024年、2024
            year_match = re.fullmatch(r'(\d{4})年?', expression)
            if year_match:
                year = int(year_match.group(1))
                start_date = datetime(year, 1, 1, 0, 0, 0)
                end_date = datetime(year, 12, 31, 23, 59, 59)
                return {
                    "success": True,
                    "expression": expression,
                    "time_type": "absolute_year",
                    "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "start_date_only": start_date.strftime("%Y-%m-%d"),
                    "end_date_only": end_date.strftime("%Y-%m-%d"),
                    "days_diff": (end_date.date() - start_date.date()).days + 1,
                    "year": year
                }

            # 匹配年月：2024年1月、2024-01
            year_month_match = re.fullmatch(r'(\d{4})年?(\d{1,2})月?', expression) or \
                              re.fullmatch(r'(\d{4})-(\d{1,2})', expression)
            if year_month_match:
                year = int(year_month_match.group(1))
                month = int(year_month_match.group(2))
                if 1 <= month <= 12:
                    start_date = datetime(year, month, 1, 0, 0, 0)
                    last_day = calendar.monthrange(year, month)[1]
                    end_date = datetime(year, month, last_day, 23, 59, 59)
                    return {
                        "success": True,
                        "expression": expression,
                        "time_type": "absolute_month",
                        "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "start_date_only": start_date.strftime("%Y-%m-%d"),
                        "end_date_only": end_date.strftime("%Y-%m-%d"),
                        "days_diff": (end_date.date() - start_date.date()).days + 1,
                        "year": year,
                        "month": month
                    }

            # 匹配月份：1月、01月
            month_match = re.fullmatch(r'(\d{1,2})月?', expression)
            if month_match:
                month = int(month_match.group(1))
                if 1 <= month <= 12:
                    year = base_date.year  # 默认使用当前年份
                    start_date = datetime(year, month, 1, 0, 0, 0)
                    last_day = calendar.monthrange(year, month)[1]
                    end_date = datetime(year, month, last_day, 23, 59, 59)
                    return {
                        "success": True,
                        "expression": expression,
                        "time_type": "absolute_month_current_year",
                        "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "start_date_only": start_date.strftime("%Y-%m-%d"),
                        "end_date_only": end_date.strftime("%Y-%m-%d"),
                        "days_diff": (end_date.date() - start_date.date()).days + 1,
                        "year": year,
                        "month": month
                    }

            return None

        except Exception as e:
            logger.error(f"Absolute time parsing failed: {e}")
            return None

    @staticmethod
    def generate_sql_time_range(time_range: Dict[str, Any], column_name: str, date_format: str = "YYYY-MM-DD") -> str:
        """生成SQL时间范围条件

        Args:
            time_range: 时间范围信息，来自parse_time_expression的结果
            column_name: 时间字段名称，如'create_time'、'order_date'等
            date_format: 数据库中日期字段的格式

        Returns:
            SQL WHERE条件字符串
        """
        try:
            if not time_range.get("success"):
                logger.warning(f"Time range parsing failed: {time_range.get('error')}")
                return ""

            start_date = time_range.get("start_date_only", "")
            end_date = time_range.get("end_date_only", "")

            if not start_date or not end_date:
                logger.warning("Invalid time range: missing start or end date")
                return ""

            # 根据不同的日期格式生成SQL条件
            if date_format.upper() == "YYYY-MM-DD":
                date_column = f"DATE({column_name})"
            elif date_format.upper() == "DATETIME":
                date_column = column_name
            else:
                # 默认使用DATE函数
                date_column = f"DATE({column_name})"

            # 生成SQL条件
            if start_date == end_date:
                return f"{date_column} = '{start_date}'"
            else:
                return f"{date_column} BETWEEN '{start_date}' AND '{end_date}'"

        except Exception as e:
            logger.error(f"SQL time condition generation failed: {e}")
            return ""

    @staticmethod
    def extract_time_expressions(question: str) -> List[str]:
        """从问题中提取时间表达式"""
        import re

        # 定义时间表达式模式 - 按优先级排序，更具体的模式在前
        patterns = [
            # 完整的相对时间表达式（优先匹配，避免拆分）
            r'过去\s*\d+[年天]|最近\s*\d+[年天]|前\s*\d+[年天]|未来\s*\d+[年天]|后\s*\d+[年天]|接下来\s*\d+[年天]',
            r'过去\s*\d+[个]?月|最近\s*\d+[个]?月|前\s*\d+[个]?月|未来\s*\d+[个]?月|后\s*\d+[个]?月|接下来\s*\d+[个]?月',
            r'过去\s*[一二三四五六七八九十百千万两]+[年天]|最近\s*[一二三四五六七八九十百千万两]+[年天]|前\s*[一二三四五六七八九十百千万两]+[年天]|未来\s*[一二三四五六七八九十百千万两]+[年天]|后\s*[一二三四五六七八九十百千万两]+[年天]|接下来\s*[一二三四五六七八九十百千万两]+[年天]',
            r'过去\s*[一二三四五六七八九十百千万两]+[个]?月|最近\s*[一二三四五六七八九十百千万两]+[个]?月|前\s*[一二三四五六七八九十百千万两]+[个]?月|未来\s*[一二三四五六七八九十百千万两]+[个]?月|后\s*[一二三四五六七八九十百千万两]+[个]?月|接下来\s*[一二三四五六七八九十百千万两]+[个]?月',
            r'近\s*\d+[年天]|近\s*[一二三四五六七八九十百千万两]+[年天]',  # 近1年、近30天、近一年、近两年等
            r'近\s*\d+[个]?月|近\s*[一二三四五六七八九十百千万两]+[个]?月',  # 近1个月、近两个月

            # 基础时间单位
            r'今天|今日|昨天|昨日|明天|明日|前天|后天',
            r'本月|这个月|当月|上月|上个月|下月|下个月',
            r'本年|今年|当年|去年|上年|明年',
            r'本季度|这个季度|当季度|上季度|下季度',
            r'本周|这周|上周|上个星期|下周|下个星期',

            # 绝对时间（需要完整的年月格式）
            r'\d{4}年\d{1,2}月?|\d{4}年|\d{4}-\d{1,2}',

            # 月份（但需要上下文，避免单独数字）
            r'\d{1,2}个?月(?![0-9])',  # 支持"1个月"、"两个月"
            r'[一二三四五六七八九十百千万两]+个?月(?![0-9])',  # 支持"一个月"、"两个月"
        ]

        expressions = []
        for pattern in patterns:
            matches = re.findall(pattern, question)
            for match in matches:
                # 过滤掉单独的数字（如 "1" 而不是 "1月"）
                if re.match(r'^\d+$', match.strip()):
                    continue
                # 过滤掉太短的匹配（至少2个字符）
                if len(match.strip()) < 2:
                    continue
                expressions.append(match.strip())

        return list(set(expressions))  # 去重

    @staticmethod
    def identify_time_columns(table_schemas: str) -> List[str]:
        """识别表结构中的时间字段"""
        time_column_patterns = [
            r'.*time.*', r'.*date.*', r'.*created.*', r'.*updated.*',
            r'.*add.*', r'.*modify.*', r'.*start.*', r'.*end.*',
            r'.*begin.*', r'.*finish.*', r'.*complete.*', r'.*order.*',
            r'.*pay.*', r'.*deliver.*', r'.*ship.*', r'.*return.*'
        ]

        time_columns = []
        lines = table_schemas.split('\n')

        for line in lines:
            line = line.strip()
            if line and not line.startswith('表名') and not line.startswith('字段') and not line.startswith('--'):
                # 提取字段名 - 处理格式：  column_name (TYPE) -- comment
                if '  ' in line and '(' in line:
                    parts = line.split('  ')
                    if parts:
                        column_part = parts[0].strip()
                        if column_part:
                            column_name = column_part
                            # 检查是否匹配时间字段模式
                            for pattern in time_column_patterns:
                                if re.match(pattern, column_name, re.IGNORECASE):
                                    time_columns.append(column_name)
                                    break

        return list(set(time_columns))  # 去重

# 全局实例
_time_utils_instance = None

def get_time_utils() -> TimeUtils:
    """获取时间工具单例实例"""
    global _time_utils_instance
    if _time_utils_instance is None:
        _time_utils_instance = TimeUtils()
    return _time_utils_instance