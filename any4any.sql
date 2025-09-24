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

