--
-- Entity Store Schema
--


--
-- Table structure for table `entities`
--
create table if not exists `entities` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `kind` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `kind_key` (`kind`)
) DEFAULT CHARSET=utf8;


--
-- Table structure for table `attributes`
--
create table if not exists `attributes` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `kind` varchar(100) NOT NULL,
  `row_id` int unsigned not null,
  `attribute` varchar(100),
  `datatype` varchar(30),
  `value` longtext,
  PRIMARY KEY (`id`),
  KEY `row_id_key` (`row_id`),
  KEY `kind_key` (`kind`),
  KEY `kv` (`kind`, `attribute`, `value`(100))
) DEFAULT CHARSET=utf8;
