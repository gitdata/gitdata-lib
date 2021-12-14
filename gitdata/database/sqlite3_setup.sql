
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
