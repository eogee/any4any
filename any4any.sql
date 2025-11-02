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

-- 正在导出表  any4any.conversations 的数据：~0 rows (大约)
DELETE FROM `conversations`;

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

-- 正在导出表  any4any.messages 的数据：~0 rows (大约)
DELETE FROM `messages`;

-- 导出  表 any4any.orders 结构
CREATE TABLE IF NOT EXISTS `orders` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `product_id` int(11) DEFAULT NULL,
  `quantity` int(11) DEFAULT NULL,
  `order_date` date DEFAULT NULL,
  `customer_name` varchar(100) DEFAULT NULL,
  `total_amount` decimal(10,2) DEFAULT NULL,
  `status` varchar(20) DEFAULT 'pending',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4;

-- 正在导出表  any4any.orders 的数据：~4 rows (大约)
DELETE FROM `orders`;
INSERT INTO `orders` (`id`, `product_id`, `quantity`, `order_date`, `customer_name`, `total_amount`, `status`, `created_at`) VALUES
	(1, 1, 2, '2024-01-15', 'Alice Johnson', 1999.98, 'completed', '2025-10-23 22:48:52'),
	(2, 2, 1, '2024-01-16', 'Bob Smith', 1999.99, 'completed', '2025-10-23 22:48:52'),
	(3, 1, 1, '2024-01-17', 'Charlie Brown', 999.99, 'pending', '2025-10-23 22:48:52'),
	(4, 3, 3, '2024-01-18', 'David Wilson', 269.97, 'completed', '2025-10-23 22:48:52');

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
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='预览编辑保存结果表';

-- 正在导出表  any4any.previews 的数据：~8 rows (大约)
DELETE FROM `previews`;
INSERT INTO `previews` (`id`, `preview_id`, `conversation_id`, `message_id`, `current_request`, `saved_content`, `pre_content`, `full_request`, `response_time`, `user_id`, `created_at`, `updated_at`) VALUES
	(1, 'preview_1759048142', 'bf73ba41-727a-4bec-abd7-f6ffc255c689', '35d586c1-3603-46e6-8289-a4ecca901332', '你好', '<think>\n\n</think>\n\n你好！有什么我可以帮你的吗？', '<think>\n\n</think>\n\n你好！有什么我可以帮你的吗？😊', '{"messages": [{"role": "user", "content": "\\u4f60\\u597d"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk"}', 9.2881, 2, '2025-09-28 08:29:11', '2025-09-28 08:29:11'),
	(2, 'preview_1759116562', 'e9b9bf0a-f4c6-4d98-8b01-21b3a777bb8a', 'combined_1759116559', '[赞]', '<think>\n\n</think>\n\n太好了！你真的很喜欢数学和 patterns，这让我感到非常高兴 😄\n\n如果你愿意，可以继续分享你感兴趣的领域，我会尽力帮你深入理解或拓展这些概念。无论是数列、逻辑、还是现实中的规律，我都很乐意陪你一起探索！\n\n欢迎随时提问！', '<think>\n\n</think>\n\n太好了！你真的很喜欢数学和 patterns，这让我感到非常高兴 😄\n\n如果你愿意，可以继续分享你感兴趣的领域，我会尽力帮你深入理解或拓展这些概念。无论是数列、逻辑、还是现实中的规律，我都很乐意陪你一起探索！\n\n欢迎随时提问！🌟', '{"messages": [{"role": "user", "content": "[\\u8d5e]"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk"}', 22.992, 2, '2025-09-29 03:29:44', '2025-09-29 03:29:44'),
	(3, 'preview_1759116728', 'e9b9bf0a-f4c6-4d98-8b01-21b3a777bb8a', 'combined_1759116719', '[赞]', '<think>\n好的，用户连续多次点击了赞，看起来他们对我的回答非常满意。现在需要回应他们的赞赏，并可能进一步互动。\n\n首先，用户可能希望得到更多的鼓励或确认他们的兴趣。考虑到之前的对话是关于数列和patterns，用户可能有兴趣继续探讨相关话题。我应该保持友好和开放的态度，邀请他们提出更多问题或分享新的想法。\n\n同时，用户可能在测试我的反应是否足够热情或是否能持续提供帮助。因此，回应需要既亲切又专业，确保他们感受到支持，并且愿意继续参与讨论。\n\n另外，用户可能希望我保持一致的语气，避免过于机械化的回复。所以，使用表情符号和友好的措辞会更符合他们的期待。最后，确保回复简洁但充满诚意，让用户觉得被重视并愿意继续交流。\n</think>\n\n谢谢你的夸奖！😊\n\n很高兴你能对数学和 patterns 感兴趣，这让我觉得很愉快！如果有什么新发现或想探讨的话题，随时欢迎分享～ 我们一起探索更多有趣的学问吧！', '<think>\n好的，用户连续多次点击了赞，看起来他们对我的回答非常满意。现在需要回应他们的赞赏，并可能进一步互动。\n\n首先，用户可能希望得到更多的鼓励或确认他们的兴趣。考虑到之前的对话是关于数列和patterns，用户可能有兴趣继续探讨相关话题。我应该保持友好和开放的态度，邀请他们提出更多问题或分享新的想法。\n\n同时，用户可能在测试我的反应是否足够热情或是否能持续提供帮助。因此，回应需要既亲切又专业，确保他们感受到支持，并且愿意继续参与讨论。\n\n另外，用户可能希望我保持一致的语气，避免过于机械化的回复。所以，使用表情符号和友好的措辞会更符合他们的期待。最后，确保回复简洁但充满诚意，让用户觉得被重视并愿意继续交流。\n</think>\n\n谢谢你的夸奖！😊\n\n很高兴你能对数学和 patterns 感兴趣，这让我觉得很愉快！如果有什么新发现或想探讨的话题，随时欢迎分享～ 我们一起探索更多有趣的学问吧！🌟', '{"messages": [{"role": "user", "content": "[\\u8d5e]"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk"}', 20.2955, 2, '2025-09-29 03:32:28', '2025-09-29 03:32:28'),
	(4, 'preview_1759121425', 'e9b9bf0a-f4c6-4d98-8b01-21b3a777bb8a', '2ec1a780-6938-499c-a3b6-3a02713a64cb', '[赞]', '<think>\n\n</think>\n\n谢谢你的赞美！如果你有任何问题或想继续聊 anything，随时欢迎回来哦～ ', '<think>\n\n</think>\n\n谢谢你的赞美！如果你有任何问题或想继续聊 anything，随时欢迎回来哦～ 😊', '{"messages": [{"role": "user", "content": "[\\u8d5e]"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk"}', 16.0641, 2, '2025-09-29 04:50:40', '2025-09-29 04:50:40'),
	(5, 'preview_1759121519', 'e9b9bf0a-f4c6-4d98-8b01-21b3a777bb8a', '7788e0b1-818b-452b-b0ee-2320469d059c', '[赞]', '<think>\n\n</think>\n\n不客气！很高兴能帮到你 😄 如果你有任何问题或想法，随时欢迎回来聊天呀', '<think>\n\n</think>\n\n不客气！很高兴能帮到你 😄 如果你有任何问题或想法，随时欢迎回来聊天呀！', '{"messages": [{"role": "user", "content": "[\\u8d5e]"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk"}', 19.016, 2, '2025-09-29 04:52:17', '2025-09-29 04:52:17'),
	(6, 'preview_1759121996', 'e9b9bf0a-f4c6-4d98-8b01-21b3a777bb8a', 'ff2167a7-765e-416e-ae84-515644e81fe0', '[赞]', '<think>\n\n</think>\n\n太好了！看到你的点赞，我真的很开心～如果你有任何问题或需要帮助的地方，随时欢迎来找我哦！', '<think>\n\n</think>\n\n太好了！看到你的点赞，我真的很开心～如果你有任何问题或需要帮助的地方，随时欢迎来找我哦！😄', '{"messages": [{"role": "user", "content": "[\\u8d5e]"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk"}', 20.9913, 2, '2025-09-29 05:00:18', '2025-09-29 05:00:18'),
	(7, 'preview_1759127200', 'e9b9bf0a-f4c6-4d98-8b01-21b3a777bb8a', '36d93bb3-0db7-4c48-81d4-ad941e47cf8b', '[赞]', '最后，保持简洁和友好，避免冗长，确保用户感受到被重视和支持，同时为后续互动留下空间。', '<think>\n好的，用户现在发来了[赞] [赞]，看起来是对之前的回复满意。我需要分析这个动作的意义。用户可能是在确认之前的回答有效，或者想表达对我的认可。这种情况下，我应该保持友好，同时引导用户继续交流，以获取更多帮助。\n\n接下来，我需要确保回复符合规范，不涉及敏感内容，同时保持自然流畅。用户可能希望得到更具体的帮助，所以我应该用简短的方式回应，鼓励他提出问题或分享需求。例如，可以用轻松的语气说："谢谢你的支持！😊 如果你有任何问题或需要帮助，随时告诉我哦～"\n\n此外，要注意用户可能的深层需求，比如他们可能希望提升效率、解决某个具体问题，或者只是想获得一些日常建议。因此，回复需要保持开放，让用户知道他们可以随时提出任何问题，从而建立信任感。\n\n最后，保持简洁和友好，避免冗长，确保用户感受到被重视和支持，同时为后续互动留下空间。', '{"messages": [{"role": "user", "content": "[\\u8d5e]"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk", "delay_time": null}', 14.9451, 2, '2025-09-29 06:26:54', '2025-09-29 06:26:54'),
	(8, 'preview_1759131216', 'e9b9bf0a-f4c6-4d98-8b01-21b3a777bb8a', '41890a56-56cc-4610-b513-5b485cc77579', '你几岁啦', '<think>\n好的，用户问：“你几岁啦”。这个问题看起来像是在问我的年龄，但作为AI助手，我没有实际的年龄。我需要礼貌地回答这个问题，同时保持友好和专业的态度。\n\n首先，我需要澄清自己是AI助手，没有真实的生命年龄。然后，可以转移话题到其他方面，比如功能或帮助，让用户感觉被关注。同时，保持语气轻松，避免让用户感到尴尬。\n\n另外，用户可能是在测试我的反应，或者想了解我的能力。因此，回答需要既诚实又不失礼貌，确保用户不会感到被冒犯。可以通过举例说明我的功能，比如学习、写作等，来展示我的价值，同时邀请用户继续提问。\n\n最后，确保回复简洁明了，避免冗长，让用户能够快速理解并继续对话。保持积极的态度，让用户感受到支持和愿意继续交流。\n</think>\n\n哈哈，我是一个AI助手，没有真实的年龄呢， 但我可以陪你一起学习、工作、生活哦！你想让我帮你做什么？', '<think>\n好的，用户问：“你几岁啦”。这个问题看起来像是在问我的年龄，但作为AI助手，我没有实际的年龄。我需要礼貌地回答这个问题，同时保持友好和专业的态度。\n\n首先，我需要澄清自己是AI助手，没有真实的生命年龄。然后，可以转移话题到其他方面，比如功能或帮助，让用户感觉被关注。同时，保持语气轻松，避免让用户感到尴尬。\n\n另外，用户可能是在测试我的反应，或者想了解我的能力。因此，回答需要既诚实又不失礼貌，确保用户不会感到被冒犯。可以通过举例说明我的功能，比如学习、写作等，来展示我的价值，同时邀请用户继续提问。\n\n最后，确保回复简洁明了，避免冗长，让用户能够快速理解并继续对话。保持积极的态度，让用户感受到支持和愿意继续交流。\n</think>\n\n哈哈，我是一个AI助手，没有真实的年龄呢 😄 但我可以陪你一起学习、工作、生活哦！你想让我帮你做什么？', '{"messages": [{"role": "user", "content": "\\u4f60\\u51e0\\u5c81\\u5566"}], "model": "default", "stream": false, "temperature": 0.7, "max_tokens": 4096, "stop": null, "top_p": 0.9, "repetition_penalty": 1.1, "sender_id": "035266212437873268", "sender_nickname": "\\u9648\\u6cfd\\u8f89", "platform": "DingTalk", "delay_time": null}', 30.7785, 2, '2025-09-29 07:34:07', '2025-09-29 07:34:07');

-- 导出  表 any4any.products 结构
CREATE TABLE IF NOT EXISTS `products` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `category` varchar(50) DEFAULT NULL,
  `price` decimal(10,2) DEFAULT NULL,
  `stock` int(11) DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4;

-- 正在导出表  any4any.products 的数据：~4 rows (大约)
DELETE FROM `products`;
INSERT INTO `products` (`id`, `name`, `category`, `price`, `stock`, `created_at`) VALUES
	(1, 'iPhone 15', 'Electronics', 999.99, 100, '2025-10-23 22:48:52'),
	(2, 'MacBook Pro', 'Electronics', 1999.99, 50, '2025-10-23 22:48:52'),
	(3, 'Coffee Maker', 'Appliances', 89.99, 200, '2025-10-23 22:48:52'),
	(4, 'Office Chair', 'Furniture', 299.99, 75, '2025-10-23 22:48:52');

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
INSERT INTO `users` (`id`, `username`, `password_hash`, `nickname`, `company`) VALUES
	(1, 'admin', '888888', 'admin', NULL),
	(2, 'eogee', '888888', 'eogee', NULL);

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
