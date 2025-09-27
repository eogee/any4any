-- --------------------------------------------------------
-- 主机:                           127.0.0.1
-- 服务器版本:                        5.7.26 - MySQL Community Server (GPL)
-- 服务器操作系统:                      Win64
-- HeidiSQL 版本:                  12.11.0.7065
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- 导出 any4any 的数据库结构
CREATE DATABASE IF NOT EXISTS `any4any` /*!40100 DEFAULT CHARACTER SET utf8 COLLATE utf8_unicode_ci */;
USE `any4any`;

-- 导出  表 any4any.conversations 结构
CREATE TABLE IF NOT EXISTS `conversations` (
  `conversation_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '会话唯一标识ID',
  `sender` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '发送者唯一标识',
  `user_nick` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户昵称或显示名称',
  `platform` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '来源平台(如: wechat, web, app等)',
  `created_time` datetime NOT NULL COMMENT '会话创建时间',
  `last_active` datetime NOT NULL COMMENT '会话最后活跃时间',
  `message_count` int(11) DEFAULT '0' COMMENT '会话中的消息总数',
  PRIMARY KEY (`conversation_id`),
  KEY `idx_user_platform` (`sender`,`user_nick`,`platform`) COMMENT '用户平台联合索引',
  KEY `idx_platform` (`platform`) COMMENT '平台索引',
  KEY `idx_last_active` (`last_active`) COMMENT '最后活跃时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话主表 - 存储会话基本信息';

-- 正在导出表  any4any.conversations 的数据：~0 rows (大约)
DELETE FROM `conversations`;

-- 导出  表 any4any.messages 结构
CREATE TABLE IF NOT EXISTS `messages` (
  `message_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '消息唯一标识ID',
  `conversation_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属会话ID',
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '消息内容',
  `sender_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '发送者类型(user-用户, assistant-助手)',
  `timestamp` datetime NOT NULL COMMENT '消息发送时间',
  `sequence_number` int(11) NOT NULL COMMENT '消息在会话中的顺序号',
  PRIMARY KEY (`message_id`),
  KEY `idx_conversation` (`conversation_id`) COMMENT '会话ID索引',
  KEY `idx_timestamp` (`timestamp`) COMMENT '消息时间索引',
  KEY `idx_sequence` (`conversation_id`,`sequence_number`) COMMENT '会话消息顺序索引',
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`conversation_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表 - 存储所有对话消息内容';

-- 正在导出表  any4any.messages 的数据：~0 rows (大约)
DELETE FROM `messages`;

-- 导出  表 any4any.previews 结构
CREATE TABLE IF NOT EXISTS `previews` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `preview_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '请求预览ID',
  `conversation_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '会话ID',
  `message_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '对话ID',
  `current_request` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '当前请求内容',
  `saved_content` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '编辑保存后的内容',
  `pre_content` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '编辑前的内容',
  `full_request` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '历史全部请求及响应内容',
  `response_time` float NOT NULL COMMENT '响应用时(秒)',
  `user_id` int(11) NOT NULL COMMENT '响应人员ID',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='预览编辑保存结果表';

-- 正在导出表  any4any.previews 的数据：~0 rows (大约)
DELETE FROM `previews`;

-- 导出  表 any4any.users 结构
CREATE TABLE IF NOT EXISTS `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `username` varchar(50) COLLATE utf8_unicode_ci NOT NULL COMMENT '用户名',
  `password_hash` varchar(50) COLLATE utf8_unicode_ci NOT NULL COMMENT '密码',
  `nickname` varchar(50) CHARACTER SET utf32 COLLATE utf32_unicode_ci DEFAULT NULL COMMENT '昵称',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci ROW_FORMAT=DYNAMIC COMMENT='用户表';

-- 正在导出表  any4any.users 的数据：~2 rows (大约)
DELETE FROM `users`;
INSERT INTO `users` (`id`, `username`, `password_hash`, `nickname`) VALUES
	(1, 'admin', '888888', 'admin'),
	(2, 'eogee', '888888', 'eogee');

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
