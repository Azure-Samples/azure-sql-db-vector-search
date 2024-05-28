# EF Core Vector Sample

**Work in progress**

Create a .env file from `.env.example` and fill in the required values, then run the database migration to create the database tables

```bash
dotnet tool install --global dotnet-ef
dotnet add package Microsoft.EntityFrameworkCore.Design
dotnet ef database update
```

Run the application

```bash
dotnet run
``` 
