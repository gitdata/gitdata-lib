--
-- Sqlite3 Create Test Tables
--

drop table if exists `person`;
create table if not exists `person` (
    `id` integer not null primary key autoincrement,
    `name` varchar(100),
    `age` smallint,
    `kids` smallint,
    `birthdate` date
);

drop table if exists `account`;
create table if not exists `account` (
    `account_id` integer not null primary key autoincrement,
    `name` varchar(100),
    `added` date
);

drop table if exists `entities`;
create table if not exists `entities` (
  `id` integer NOT NULL PRIMARY KEY autoincrement
,  `kind` varchar(100) NOT NULL
);

drop table if exists `attributes`;
create table if not exists `attributes` (
  `id` integer NOT NULL PRIMARY KEY autoincrement
,  `kind` varchar(100) NOT NULL
,  `row_id` integer  not null
,  `attribute` varchar(100)
,  `datatype` varchar(30)
,  `value` mediumtext
);
