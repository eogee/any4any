-- --------------------------------------------------------
-- 主机:                           localhost
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

-- 正在导出表  any4any.conversations 的数据：~1 rows (大约)
DELETE FROM `conversations`;
INSERT INTO `conversations` (`conversation_id`, `sender`, `user_nick`, `platform`, `created_time`, `last_active`, `message_count`) VALUES
	('80361d2f-fb78-4ed0-913a-2671b9e34a96', 'admin', 'admin', 'any4chat', '2025-11-06 00:57:40', '2025-11-06 01:04:10', 6);

-- 导出  表 any4any.messages 结构
CREATE TABLE IF NOT EXISTS `messages` (
  `message_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '消息唯一标识ID',
  `conversation_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所属会话ID',
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '消息内容',
  `sender_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '发送者类型(user-用户, assistant-助手)',
  `is_timeout` tinyint(4) DEFAULT '0' COMMENT '是否为超时自动回复',
  `timestamp` datetime NOT NULL COMMENT '消息发送时间',
  `sequence_number` int(11) NOT NULL COMMENT '消息在会话中的顺序号',
  PRIMARY KEY (`message_id`),
  KEY `idx_conversation` (`conversation_id`) COMMENT '会话ID索引',
  KEY `idx_timestamp` (`timestamp`) COMMENT '消息时间索引',
  KEY `idx_sequence` (`conversation_id`,`sequence_number`) COMMENT '会话消息顺序索引',
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`conversation_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表 - 存储所有对话消息内容';

-- 正在导出表  any4any.messages 的数据：~6 rows (大约)
DELETE FROM `messages`;
INSERT INTO `messages` (`message_id`, `conversation_id`, `content`, `sender_type`, `is_timeout`, `timestamp`, `sequence_number`) VALUES
	('1fcfb36a-3d7f-4b2f-a0e8-06d920619520', '80361d2f-fb78-4ed0-913a-2671b9e34a96', '退出登录', 'user', 0, '2025-11-06 00:57:54', 1),
	('5a48ec7b-bedd-413d-a30a-048bce0dcf45', '80361d2f-fb78-4ed0-913a-2671b9e34a96', '退出登录', 'user', 0, '2025-11-06 01:03:33', 5),
	('80b9d4b7-9ede-4942-8e83-d98ffba38949', '80361d2f-fb78-4ed0-913a-2671b9e34a96', '您已成功退出登录。', 'assistant', 0, '2025-11-06 00:58:31', 2),
	('889cbd53-8473-49a4-9b64-8829981207c2', '80361d2f-fb78-4ed0-913a-2671b9e34a96', '登录', 'user', 0, '2025-11-06 01:02:41', 3),
	('bb9c93c7-35a8-4aba-886c-0133ceef7ee7', '80361d2f-fb78-4ed0-913a-2671b9e34a96', '登录已完成。', 'assistant', 0, '2025-11-06 01:03:23', 4),
	('ed0ab3c5-04f3-4844-a1a1-f7671b728c17', '80361d2f-fb78-4ed0-913a-2671b9e34a96', '您已成功退出登录。', 'assistant', 0, '2025-11-06 01:04:10', 6);

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
  `company` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL COMMENT '公司名称',
  `nickname` varchar(50) CHARACTER SET utf32 COLLATE utf32_unicode_ci DEFAULT NULL COMMENT '昵称',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci ROW_FORMAT=DYNAMIC COMMENT='用户表';

-- 正在导出表  any4any.users 的数据：~2 rows (大约)
DELETE FROM `users`;
INSERT INTO `users` (`id`, `username`, `password_hash`, `company`, `nickname`) VALUES
	(1, 'admin', '888888', '书昀', 'admin'),
	(2, 'eogee', '888888', NULL, 'eogee');

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
