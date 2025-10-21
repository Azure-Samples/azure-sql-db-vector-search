using Microsoft.Data;
using Microsoft.Data.SqlClient;
using Microsoft.Data.SqlTypes;
using OpenAI.Embeddings;
using Azure.AI.OpenAI;
using Azure;
using System.Data;
using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using DotNetEnv;
using System.Security.Cryptography;

namespace SqlServer.NativeVectorSearch.Samples
{
    /// <summary>
    /// To run the samples, you need to set the following environment variables:
    /// - SqlConnStr: SQL Server connection string
    /// - EmbeddingModelName: Name of the embedding model
    /// - UseAzureOpenAI: Set to "true" to use Azure OpenAI, "false" or omit for OpenAI (default: false)
    /// 
    /// For OpenAI:
    /// - ApiKey: Your OpenAI API key
    /// 
    /// For Azure OpenAI:
    /// - AzureOpenAIEndpoint: Your Azure OpenAI endpoint (e.g., https://your-resource.openai.azure.com/)
    /// - AzureOpenAIKey: Your Azure OpenAI API key
    /// 
    /// You also need to create a table in the database with the following schema:
    ///
    /// CREATE SCHEMA test AUTHORIZATION dbo;
    /// DROP TABLE IF EXISTS test.Vectors;
    /// CREATE TABLE test.Vectors
    /// (
    ///     [Id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    ///     [Text] NVARCHAR(MAX) NULL,
    ///     [VectorShort] VECTOR(3)  NULL,
    ///     [Vector] VECTOR(1536)  NULL
    /// ) ON [PRIMARY];
    /// </summary>
    internal class Program
    {
        private static Random _rnd = new Random();
        private static string _cConnStr;
        private static string _cEmbeddingModel;
        private static string? _cApiKey;
        private static bool _cUseAzureOpenAI;
        private static string? _cAzureOpenAIEndpoint;
        private static string? _cAzureOpenAIKey;
        private static string _cTableName = "Vectors";

        static Program()
        {
            Env.Load();

            // Note, you can use launchSettings to set the required environment variables.
            _cConnStr = Environment.GetEnvironmentVariable("SqlConnStr")!;
            _cEmbeddingModel = Environment.GetEnvironmentVariable("EmbeddingModelName")!;
            _cUseAzureOpenAI = bool.TryParse(Environment.GetEnvironmentVariable("UseAzureOpenAI"), out var useAzure) && useAzure;

            if (_cUseAzureOpenAI)
            {
                _cAzureOpenAIEndpoint = Environment.GetEnvironmentVariable("AzureOpenAIEndpoint")!;
                _cAzureOpenAIKey = Environment.GetEnvironmentVariable("AzureOpenAIKey")!;
                Console.WriteLine($"Using Azure OpenAI with endpoint: {_cAzureOpenAIEndpoint}");
            }
            else
            {
                _cApiKey = Environment.GetEnvironmentVariable("ApiKey")!;
                Console.WriteLine("Using OpenAI");
            }
        }

        static async Task Main(string[] args)
        {
            Console.WriteLine("Running CreateAndInsertVectorsAsync()...");
            await CreateAndInsertVectorsAsync();

            Console.WriteLine("Running CreateAndInsertEmbeddingAsync()...");
            await CreateAndInsertEmbeddingAsync();

            Console.WriteLine("Running ReadVectorsAsync()...");
            await ReadVectorsAsync();

            Console.WriteLine("Running FindSimilarAsync()...");
            await FindSimilarAsync();

            Console.WriteLine("Running GenerateTestDocumentsAsync()...");
            await GenerateTestDocumentsAsync();

            Console.WriteLine("Running ClassifyDocumentsAsync()...");
            await ClassifyDocumentsAsync();

            Console.WriteLine("Running GenerateRandomVectorsAsync()...");
            await GenerateRandomVectorsAsync();
        }

        /// <summary>
        /// Demonstrates how to create vectors and insert them into the table. 
        /// For the sake of simplicity, the method inserts two vectors each 3 dimensions.
        /// </summary>
        /// <returns></returns>
        public static async Task CreateAndInsertVectorsAsync()
        {
            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                // Vector is inserted in the column '[VectorShort] VECTOR(3)  NULL'
                string sql = $"INSERT INTO [test].[{_cTableName}] ([VectorShort]) VALUES (@Vector)";

                SqlCommand command = new SqlCommand(sql, connection);

                // Demonstrates how to use the new SqlVector<T> type to insert the vector.
                command.Parameters.AddWithValue("@Vector", new SqlVector<float>(new float[] { 7.01f, 7.02f, -7.03f }));

                // Alternative way how to add the vector parameter.
                //var prm = command.Parameters.Add("@Vector", SqlDbTypeExtensions.Vector);
                //prm.Value= new SqlVector<float>( new float[] { 7.01f, 7.02f, -7.03f });

                // OBSOLETE:
                // Supported for compatibility with the old driver Microsoft.Data.SqlClient: Version < 6.1.0.
                // Insert vector as string. Note JSON array. 
                // command.Parameters.AddWithValue("@Vector", "[7.12, -2.22, 3.33]");
                // Insert vector as JSON string serialized from the float array.
                // command.Parameters.AddWithValue("@Vector", JsonSerializer.Serialize(new float[] { 4.12f, 22.22f, -3.33f }));

                connection.Open();

                var result = await command.ExecuteNonQueryAsync();

                connection.Close();
            }
        }

        /// <summary>
        /// Demonstrates how to create a embedding vector and how to insert it into the table.
        /// </summary>
        /// <returns></returns>
        public static async Task CreateAndInsertEmbeddingAsync()
        {
            EmbeddingClient client = CreateEmbeddingClient();

            // The text to be converted to a vector.
            string text = "Native Vector Search for SQL Server";

            // Generate the embedding vector by using OpenAI SDK
            var res = await client.GenerateEmbeddingsAsync(new List<string>() { text });

            OpenAIEmbedding embedding = res.Value.First();

            ReadOnlyMemory<float> embeddingVector = embedding.ToFloats();

            //
            // Following code demonstrates how to insert the vector into the column Vector:
            // [Vector] VECTOR(1536)  NULL
            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                var id = Guid.NewGuid().ToString();

                // Embedding is inserted in the column '[Vector] VECTOR(1536)  NULL'
                SqlCommand command = new SqlCommand($"INSERT INTO [test].[{_cTableName}] ([Vector], [Text]) VALUES (@Vector, @Text)", connection);

                // Demonstrates how to use the new SqlVector<T> type to insert the vector.
                command.Parameters.AddWithValue("@Vector", new SqlVector<float>(embeddingVector.ToArray()));

                //
                // OBSOLETE: Supported for compatibility with the old driver Microsoft.Data.SqlClient: Version < 6.1.0.
                //command.Parameters.AddWithValue("@Vector", JsonSerializer.Serialize(embeddingVector.ToArray()));

                command.Parameters.AddWithValue("@Text", text);

                connection.Open();

                var result = await command.ExecuteNonQueryAsync();

                connection.Close();
            }
        }

        /// <summary>
        /// It creates many random embedding vectors and inserts them into the table.
        /// </summary>
        /// <param name="howMany"></param>
        /// <returns></returns>
        public static async Task GenerateRandomVectorsAsync(int howMany = 10000)
        {
            // Just for testing, use SqlBulkCopy for better performance.            
            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                connection.Open();

                for (int i = 0; i < howMany; i++)
                {
                    string sql = $"INSERT INTO [test].[{_cTableName}] ([Vector],[Text]) VALUES  (@Vector, @Text)";

                    SqlCommand command1 = new SqlCommand(sql, connection);

                    command1.Parameters.AddWithValue("@Vector", new SqlVector<float>(CreateRandomVector()));
                    command1.Parameters.AddWithValue("@Text", i.ToString("D4"));

                    var result1 = await command1.ExecuteNonQueryAsync();
                }

                connection.Close();
            }
        }


        /// <summary>
        /// Demonstrates how to read vectors from the table.
        /// Please nite the code is not optimized. It is for demonstration purposes only to understand
        /// how to deal with the vector type.
        /// </summary>
        /// <returns></returns>

        public static async Task ReadVectorsAsync()
        {
            List<(long Id, string VectorShort, string Vector, string Text)> rows = new();

            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                var id = Guid.NewGuid().ToString();

                SqlCommand command = new SqlCommand($"Select TOP(100) * FROM [test].[{_cTableName}]", connection);

                connection.Open();

                using (SqlDataReader reader = await command.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        //
                        // Demonstrates how to read the vector as a native type.
                        var vectorShort = reader.IsDBNull(reader.GetOrdinal("VectorShort")) ?
                          SqlVector<float>.CreateNull(3) :
                          reader.GetSqlVector<float>(reader.GetOrdinal("VectorShort"));

                        var vectorEmbedding = reader.IsDBNull(reader.GetOrdinal("Vector")) ?
                            SqlVector<float>.CreateNull(1536) :
                            reader.GetSqlVector<float>(reader.GetOrdinal("Vector"));

                        //
                        // Demonstrates ow to get a float array from the vector type.
                        float[] arrShort = vectorShort.Memory.ToArray();
                        float[] arrEmbedding = vectorEmbedding.Memory.ToArray();

                        (long Id, string VectorShort, string Vector, string Text) row = new(
                            reader.GetInt32(reader.GetOrdinal("Id")),
                            string.Join(", ", arrShort),
                            string.Join(", ", arrEmbedding).Substring(0, Math.Min(75, arrEmbedding.Length)) + " ... ",
                            // OBSOLETE: Supported for compatibility with the old driver Microsoft.Data.SqlClient: Version < 6.1.0.
                            //reader.IsDBNull(reader.GetOrdinal("VectorShort")) ? "-" : reader.GetString(reader.GetOrdinal("VectorShort")),
                            //reader.IsDBNull(reader.GetOrdinal("Vector")) ? "-" : reader.GetString(reader.GetOrdinal("Vector")).Substring(0, 20) + "...",
                            reader.IsDBNull(reader.GetOrdinal("Text")) ? "-" : reader.GetString(reader.GetOrdinal("Text"))
                        );

                        rows.Add(row);
                    }
                }

                connection.Close();
            }

            foreach (var row in rows)
            {
                Console.WriteLine($"{row.Id}, {row.VectorShort}, {row.Vector}, {row.Text}");
            }
        }


        /// <summary>
        /// Calculates the distance between vectors.
        /// </summary>
        /// <returns></returns>

        public static async Task FindSimilarAsync()
        {
            List<(long Id, double Distance, string Text)> rows = new();

            var embedding = new float[] { 1.12f, 2.22f, 3.33f };

            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                var id = Guid.NewGuid().ToString();

                SqlCommand command = new SqlCommand($"Select TOP(100) Id, Text, VECTOR_DISTANCE('cosine', @Embedding, VectorShort) AS Distance FROM [test].[{_cTableName}]", connection);

                command.Parameters.AddWithValue("@Embedding", new SqlVector<float>(embedding));

                connection.Open();

                using (SqlDataReader reader = await command.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        (long Id, double distance, string Text) row = new(
                            reader.GetInt32(reader.GetOrdinal("Id")),
                            reader.IsDBNull(reader.GetOrdinal("Distance")) ? -999 : reader.GetDouble(reader.GetOrdinal("Distance")),
                            reader.IsDBNull(reader.GetOrdinal("Text")) ? "-" : reader.GetString(reader.GetOrdinal("Text"))
                        );

                        rows.Add(row);
                    }
                }

                connection.Close();
            }

            foreach (var row in rows)
            {
                Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
            }
        }



        public static readonly string[] _cities = new string[]
        {
            "New York", "Los Angeles", "Chicago", // United States
            "Toronto", "Vancouver", "Montreal", // Canada
            "Mexico City", "Guadalajara", "Monterrey", // Mexico
            "Buenos Aires", "Córdoba", "Rosario", // Argentina
            "São Paulo", "Rio de Janeiro", "Brasília", // Brazil
            "Lima", "Arequipa", "Cusco", // Peru
            "London", "Birmingham", "Manchester", // United Kingdom
            "Paris", "Marseille", "Lyon", // France
            "Berlin", "Munich", "Frankfurt", // Germany
            "Madrid", "Barcelona", "Valencia", // Spain
            "Rome", "Milan", "Naples", // Italy
            "Moscow", "Saint Petersburg", "Novosibirsk", // Russia
            "Istanbul", "Ankara", "Izmir", // Turkey
            "Cairo", "Alexandria", "Giza", // Egypt
            "Lagos", "Abuja", "Kano", // Nigeria
            "Johannesburg", "Cape Town", "Durban", // South Africa
            "Nairobi", "Mombasa", "Kisumu", // Kenya
            "Tokyo", "Osaka", "Yokohama", // Japan
            "Beijing", "Shanghai", "Shenzhen", // China
            "Seoul", "Busan", "Incheon", // South Korea
            "Mumbai", "Delhi", "Bangalore", // India
            "Bangkok", "Chiang Mai", "Pattaya", // Thailand
            "Kuala Lumpur", "George Town", "Ipoh", // Malaysia
            "Singapore", // Singapore
            "Jakarta", "Surabaya", "Bandung", // Indonesia
            "Sydney", "Melbourne", "Brisbane", // Australia
            "Auckland", "Wellington", "Christchurch", // New Zealand
            "Riyadh", "Jeddah", "Mecca", // Saudi Arabia
            "Tehran", "Mashhad", "Isfahan", // Iran
            "Baghdad", "Basra", "Erbil", // Iraq
            "Tel Aviv", "Jerusalem", "Haifa", // Israel
            "Athens", "Thessaloniki", "Patras", // Greece
            "Warsaw", "Krakow", "Wroclaw", // Poland
            "Helsinki", "Espoo", "Tampere", // Finland
            "Stockholm", "Gothenburg", "Malmo", // Sweden
            "Oslo", "Bergen", "Stavanger", // Norway
            "Amsterdam", "Rotterdam", "Utrecht", // Netherlands
            "Sarajevo", "Banja Lika", "Derventa", // Bosnia and Herzegovina
        };

        /// <summary>
        /// Classifies documents by type. It looks for invoices.
        /// </summary>
        /// <returns></returns>
        public static async Task ClassifyDocumentsAsync()
        {
            var invoicesEng = await GetMatching(20, "invoice total item");

            var invoiceGER = await GetMatching(20, "rechnung item gesammt");

            var invoiceBH = await GetMatching(20, "racun ukupno item");

            Console.WriteLine(" --- ENG ---");
            foreach (var row in invoicesEng)
            {
                Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
            }

            Console.WriteLine(" --- GER ---");
            foreach (var row in invoiceGER)
            {
                Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
            }

            Console.WriteLine(" --- BH ---");
            foreach (var row in invoiceBH)
            {
                Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
            }
        }

        /// <summary>
        /// Classifies documents by country. Note that country is not a part of any document.
        /// Invoices and Delivery notes contain both the address of the shipping of item.
        /// Classification calculates the semantic distance between the document and the country.
        /// </summary>
        /// <returns></returns>
        public static async Task ClassificationByDocumentCountry_Test()
        {
            var france = await GetMatching(20, "adress in france");

            var bosnia = await GetMatching(20, "address in bosnia");

            var usa = await GetMatching(20, "address in united states");

            Console.WriteLine(" --- FRA ---");
            foreach (var row in france)
            {
                Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
            }

            Console.WriteLine(" --- BA ---");
            foreach (var row in bosnia)
            {
                Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
            }

            Console.WriteLine(" --- USA ---");
            foreach (var row in usa)
            {
                Console.WriteLine($"{row.Id}, {row.Distance}, {row.Text}");
            }
        }
        private static async Task<List<(long Id, double Distance, string Text)>> GetMatching(int howMany, string text)
        {
            List<(long Id, double Distance, string Text)> matchingRows = new();

            EmbeddingClient client = CreateEmbeddingClient();

            var res = await client.GenerateEmbeddingsAsync(new List<string>() { text });

            ReadOnlyMemory<float> embeddingVector = res.Value.First().ToFloats();

            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                var id = Guid.NewGuid().ToString();

                SqlCommand command = new SqlCommand($"Select TOP({howMany}) Id, Text, VECTOR_DISTANCE('cosine', @Embedding, Vector) AS Distance FROM [test].[{_cTableName}] ORDER BY DISTANCE", connection);

                command.Parameters.AddWithValue("@Embedding", new SqlVector<float>(embeddingVector.ToArray()));

                connection.Open();

                using (SqlDataReader reader = await command.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        (long Id, double distance, string Text) row = new(
                            reader.GetInt32(reader.GetOrdinal("Id")),
                            reader.IsDBNull(reader.GetOrdinal("Distance")) ? -999 : reader.GetDouble(reader.GetOrdinal("Distance")),
                            reader.IsDBNull(reader.GetOrdinal("Text")) ? "-" : reader.GetString(reader.GetOrdinal("Text"))
                        );

                        matchingRows.Add(row);
                    }
                }

                connection.Close();
            }

            return matchingRows;
        }



        /// <summary>
        /// This method creates a random vector and looks up the most similar vector in the table.
        /// Elapsed average time for 
        /// 1000*    ms
        /// ------------
        /// 10:     444 
        /// 20:     500
        /// 30:     591
        /// 40:     805
        /// 50:    1003
        /// 60:    1200
        /// 70:    1414
        /// 80:    1606
        /// 90:    1790
        /// 100:   2006
        /// </summary>
        /// <returns></returns>
        public async Task LookupNearest(int loops = 100)
        {
            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                float[] vector = CreateRandomVector();

                Stopwatch sw = new Stopwatch();
                sw.Start();

                for (int i = 0; i < loops; i++)
                {
                    connection.Open();

                    SqlCommand command = new SqlCommand($"Select TOP(10) Id, VECTOR_DISTANCE('cosine', @Embedding AS Vector(1536), Vector) AS Distance FROM [test].[{_cTableName}] ORDER BY DISTANCE", connection);

                    command.Parameters.AddWithValue("@Embedding", new SqlVector<float>(vector));

                    using (var reader = await command.ExecuteReaderAsync(System.Data.CommandBehavior.CloseConnection))
                    {

                    }
                }

                sw.Stop();

                Console.WriteLine($"Elapsed average time for 50k: {sw.ElapsedMilliseconds / loops} ms");
            }
        }

        /// <summary>
        /// Creates the random vector in 1536 dimensions space.
        /// </summary>
        /// <returns></returns>
        private static float[] CreateRandomVector()
        {
            float[] vector = new float[1536];

            for (int i = 0; i < 1536; i++)
            {
                vector[i] = (float)_rnd.NextDouble();
            }

            return vector;
        }

        /// <summary>
        /// This method generates 10 fake invoices and 10 delivery statements (shipment documents).
        /// After generating the documents, the method uses the model to create an embedding vector, which
        /// will be inserted into the database along with the document text.
        /// </summary>
        public static async Task GenerateTestDocumentsAsync()
        {
            string[] customers = { "John Doe", "Jane Smith", "Alice Johnson", "Bob Lee", "Emma Davis", "Chris White",
                               "Lily Brown", "James Wilson", "Olivia King", "Michael Scott" };
            string[] items = { "Laptop", "Smartphone", "Tablet", "Monitor", "Headphones", "Keyboard",
                           "Mouse", "Printer", "External Hard Drive", "Webcam" };

            for (int i = 1; i <= 10; i++)
            {
                string filePath = $"{i.ToString("D2")}.txt";

                using (StreamWriter writer = new StreamWriter($"Invoice_{filePath}"))
                {
                    var inv = GenerateInvoice(i, customers, items, _cities);
                    await InsertVector(inv);
                    writer.WriteLine(inv);
                }

                using (StreamWriter writer = new StreamWriter($"Delivery_{filePath}"))
                {
                    var deliv = GenerateDeliveryStatement(i, customers, _cities, items);
                    await InsertVector(deliv);
                    writer.WriteLine(deliv);
                }
            }
        }

        private static string GenerateInvoice(int invoiceNumber, string[] customers, string[] items, string[] cities)
        {
            string[] invoiceNames = new string[] { "Invoice", "Racun", "Rechnung" };
            Random random = new Random();
            string customer = customers[random.Next(customers.Length)];
            DateTime date = DateTime.Now.AddDays(-random.Next(1, 30));
            string item = items[random.Next(items.Length)];
            int quantity = random.Next(1, 6);
            decimal unitPrice = Math.Round((decimal)(random.NextDouble() * (500 - 50) + 50), 2);
            decimal total = Math.Round(quantity * unitPrice, 2);

            return $@"
                    {invoiceNames[random.Next(0, invoiceNames.Length - 1)]} Number: INV-{invoiceNumber:0000}
                    Date: {date:yyyy-MM-dd}
                    Customer: {customer}
                    Address: {cities[random.Next(cities.Length - 1)]}

                    Item Description         Quantity    Unit Price    Total
                    ------------------------------------------------------------
                    {item,-22} {quantity,-10} ${unitPrice,-10} ${total}

                    ------------------------------------------------------------
                    Grand Total: ${total}
                    ";
        }

        private static string GenerateDeliveryStatement(int invoiceNumber, string[] customers, string[] cities, string[] items)
        {
            string[] statements = new string[] { "Dispatch Note", "Shipong note", "Lieferschein", "Consignment", "Delivery Receipt", "" };
            Random random = new Random();
            string customer = customers[random.Next(customers.Length)];
            DateTime date = DateTime.Now.AddDays(-random.Next(1, 30));
            string item = items[random.Next(items.Length)];
            int quantity = random.Next(1, 6);
            decimal unitPrice = Math.Round((decimal)(random.NextDouble() * (500 - 50) + 50), 2);
            decimal total = Math.Round(quantity * unitPrice, 2);

            return $@"
                    {statements[random.Next(0, statements.Length - 1)]} Number: DEL-{invoiceNumber:0000}
                    Date: {date:yyyy-MM-dd}
                    Customer: {customer}
                    Delivery Address: {cities[random.Next(cities.Length - 1)]}

                    Delivery Item: {item,-22} {quantity,-10}         
                    ";
        }

        /// <summary>
        /// Creates an EmbeddingClient based on the configuration (OpenAI or Azure OpenAI).
        /// </summary>
        /// <returns>EmbeddingClient instance</returns>
        private static EmbeddingClient CreateEmbeddingClient()
        {
            if (_cUseAzureOpenAI)
            {
                if (string.IsNullOrEmpty(_cAzureOpenAIEndpoint) || string.IsNullOrEmpty(_cAzureOpenAIKey))
                    throw new InvalidOperationException("Azure OpenAI endpoint and key must be configured when UseAzureOpenAI is true.");
                
                var azureClient = new AzureOpenAIClient(new Uri(_cAzureOpenAIEndpoint), new AzureKeyCredential(_cAzureOpenAIKey));
                return azureClient.GetEmbeddingClient(_cEmbeddingModel);
            }
            else
            {
                if (string.IsNullOrEmpty(_cApiKey))
                    throw new InvalidOperationException("OpenAI API key must be configured when UseAzureOpenAI is false.");
                
                return new EmbeddingClient(_cEmbeddingModel, _cApiKey);
            }
        }

        private static async Task InsertVector(string text)
        {
            EmbeddingClient client = CreateEmbeddingClient();

            var res = await client.GenerateEmbeddingsAsync(new List<string>() { text });

            ReadOnlyMemory<float> embeddingVector = res.Value.First().ToFloats();

            using (SqlConnection connection = new SqlConnection(_cConnStr))
            {
                string sql = $"INSERT INTO [test].[{_cTableName}] ([Vector], [Text]) VALUES (@Vector, @Text)";

                SqlCommand command1 = new SqlCommand(sql, connection);

                // Insert vector as string. Note JSON array.
                command1.Parameters.AddWithValue("@Vector", new SqlVector<float>(embeddingVector.ToArray()));
                command1.Parameters.AddWithValue("@Text", text);

                connection.Open();

                var result1 = await command1.ExecuteNonQueryAsync();

                connection.Close();
            }
        }


        #region Vector Serialization

        /// <summary>
        /// This method is used to test the performance of the vector serialization by using different approaches.
        /// Dimensions:  Avg JSON   Avg Str
        /// ---------------------------------
        ///    1536       6099,62    6809,46
        /// </summary>
        public void VectorSerialization_Tests()
        {
            Random rnd = new();

            List<float> vector = new();

            for (int i = 0; i < 1536; i++)
            {
                vector.Add((float)rnd.NextDouble() * 100);
            }

            int count = 10000;

            var vectorArray = vector.ToArray();

            List<long> jsonResults = [];
            List<long> stringResults = [];

            for (int k = 0; k < 100; k++)
            {
                Stopwatch swJson = new();
                swJson.Start();

                for (int i = 0; i < count; i++)
                {
                    var vectorString = ToVectorJsonString(vectorArray);
                }

                swJson.Stop();

                Stopwatch swString = new();
                swString.Start();

                for (int i = 0; i < count; i++)
                {
                    var vectorString = ToVectorString(vectorArray);
                }

                swString.Stop();

                jsonResults.Add(swJson.ElapsedMilliseconds);
                stringResults.Add(swString.ElapsedMilliseconds);
            }

            for (int i = 0; i < jsonResults.Count; i++)
            {
                Console.WriteLine($"j: {jsonResults[i]} s: {stringResults[i]}");
            }

            Console.WriteLine("----------------------------------------------");

            Console.WriteLine($"j: {jsonResults.Average()} s: {stringResults.Average()}");
        }

        private static string ToVectorJsonString(float[] embedding)
        {
            return JsonSerializer.Serialize(embedding);
        }

        private static string ToVectorString(float[] embedding)
        {
            StringBuilder sb = new("[");

            bool isFirst = true;

            foreach (float value in embedding)
            {
                if (!isFirst)
                {
                    _ = sb.Append(',');
                }
                else
                    isFirst = false;

                sb.Append(value.ToString(CultureInfo.InvariantCulture));
            }

            sb.Append(']');

            return sb.ToString();

        }
        #endregion
    }
}
