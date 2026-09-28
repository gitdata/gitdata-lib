CREATE DATABASE /*!32312 IF NOT EXISTS*/ `gitdata_example` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;

USE `gitdata_example`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `customers` (
  `customer_id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `email` varchar(255) NOT NULL,
  `country_code` char(2) NOT NULL,
  `joined_on` date NOT NULL,
  PRIMARY KEY (`customer_id`),
  UNIQUE KEY `customers_email_unique` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
INSERT INTO `customers` VALUES
(1,'Ada Lovelace','ada@example.test','GB','2024-01-15'),
(2,'Grace Hopper','grace@example.test','US','2024-02-20'),
(3,'Linus Torvalds','linus@example.test','FI','2024-03-10');
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `orders` (
  `order_id` int(11) NOT NULL AUTO_INCREMENT,
  `customer_id` int(11) NOT NULL,
  `ordered_at` datetime NOT NULL,
  `status` enum('new','paid','shipped','cancelled') NOT NULL,
  `total` decimal(10,2) NOT NULL,
  PRIMARY KEY (`order_id`),
  KEY `orders_customer_index` (`customer_id`),
  CONSTRAINT `orders_customer_fk` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
INSERT INTO `orders` VALUES
(1,1,'2025-01-10 09:30:00','shipped',40.50),
(2,2,'2025-01-11 14:05:00','paid',28.00),
(3,1,'2025-01-12 16:45:00','new',9.75),
(4,3,'2025-01-13 08:15:00','cancelled',12.50);
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `products` (
  `product_id` int(11) NOT NULL AUTO_INCREMENT,
  `sku` varchar(32) NOT NULL,
  `name` varchar(100) NOT NULL,
  `price` decimal(10,2) NOT NULL,
  `active` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`product_id`),
  UNIQUE KEY `products_sku_unique` (`sku`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
INSERT INTO `products` VALUES
(1,'NOTE-001','Field notebook',12.50,1),
(2,'PEN-002','Fountain pen',28.00,1),
(3,'INK-003','Blue ink bottle',9.75,0);
