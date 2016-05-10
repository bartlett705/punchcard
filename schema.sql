drop table if exists entries;
create table entries (
	in_time number primary key not null,
	out_time number not null,
	desc text
);
