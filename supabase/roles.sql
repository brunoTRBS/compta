-- Custom roles mirroring production
CREATE ROLE "app_reader" WITH INHERIT NOCREATEROLE NOCREATEDB LOGIN BYPASSRLS;
