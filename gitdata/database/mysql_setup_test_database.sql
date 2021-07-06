--
-- gitdata mysql setup test database
--
-- Run this script once to setup the database required for
-- the test suites.
--

create database if not exists gitdatatest;

create user testuser identified by 'password';
grant all on gitdatatest.* to testuser@'%';


