/*
	Create sample table
*/
drop table if exists dbo.sample_text;
create table dbo.sample_text
(
	id int identity not null primary key,
	content nvarchar(max) null,
	embedding vector(1536) null,
	[vectors_update_info] nvarchar(max) null 
)
go

/*
	Create trigger to update embeddings
	when "content" column is changed
*/
create or alter trigger sample_text_generate_embeddings
on dbo.sample_text 
after insert, update
as
set nocount on;

if not(update(content)) return;

declare c cursor fast_forward read_only
for select [id], [content] from inserted
order by id;

declare @id int, @content nvarchar(max);

open c;
fetch next from c into @id, @content
while @@fetch_status = 0
begin
	begin try
		declare @retval int;
  
		if update(content) begin		
			declare @embedding vector(1536);
			exec @retval = [dbo].[get_embedding] '<deployment-name>', @content, @embedding output with result sets none
			update [dbo].[sample_text] set embedding = @embedding where id = @id
		end

		update [dbo].[sample_text] set [vectors_update_info] = json_object('status':'updated', 'timestamp':CURRENT_TIMESTAMP)
	end try
	begin catch
		update [dbo].[sample_text] set [vectors_update_info] = json_object('status':'error', 'timestamp':CURRENT_TIMESTAMP)
	end catch
	fetch next from c into @id, @content

end
close c
deallocate c
go

/*
	Test trigger
*/
insert into dbo.sample_text (content) values ('The foundation series from Isaac Asimov')
go

select * from dbo.sample_text
go
