-- any4any 的数据库结构
CREATE DATABASE IF NOT EXISTS `any4any` /*!40100 DEFAULT CHARACTER SET utf8 COLLATE utf8_unicode_ci */;
USE `any4any`;

-- 表 any4any.users 结构
CREATE TABLE IF NOT EXISTS `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `username` varchar(50) COLLATE utf8_unicode_ci NOT NULL COMMENT '用户名',
  `password_hash` varchar(50) COLLATE utf8_unicode_ci NOT NULL COMMENT '密码',
  `nickname` varchar(50) CHARACTER SET utf32 COLLATE utf32_unicode_ci DEFAULT NULL COMMENT '昵称',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci ROW_FORMAT=DYNAMIC COMMENT='用户表';

-- any4any.users 的数据：~2 rows (大约)
DELETE FROM `users`;
INSERT INTO `users` (`id`, `username`, `password_hash`, `nickname`) VALUES
	(1, 'admin', 'qq110748', 'admin');

CREATE TABLE `previews` (
	`id` INT(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
	`preview_id` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '预览ID' COLLATE 'utf8mb4_unicode_ci',
	`edited_content` MEDIUMTEXT NOT NULL COMMENT '编辑保存后的内容' COLLATE 'utf8mb4_unicode_ci',
	`pre_content` MEDIUMTEXT NOT NULL COMMENT '编辑前的内容' COLLATE 'utf8mb4_unicode_ci',
	`is_edited` TINYINT(1) NOT NULL DEFAULT '0' COMMENT '是否经过编辑',
	`full_request` MEDIUMTEXT NOT NULL COMMENT '历史全部请求及响应内容' COLLATE 'utf8mb4_unicode_ci',
	`last_request` MEDIUMTEXT NOT NULL COMMENT '当前请求内容' COLLATE 'utf8mb4_unicode_ci',
	`created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
	`updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
	PRIMARY KEY (`id`) USING BTREE
)
COMMENT='预览编辑保存结果'
COLLATE='utf8mb4_unicode_ci'
ENGINE=InnoDB
AUTO_INCREMENT=2
;