import { Connection, Request, TYPES } from "tedious";
import {
  DefaultAzureCredential,
  getBearerTokenProvider,
  type AccessToken,
} from "@azure/identity";
import { AzureOpenAI } from "openai";
import { loadConfig } from "./config.js";

// ---------------------------------------------------------------------------
// Sample hotel data
// ---------------------------------------------------------------------------
const hotels = [
  {
    name: "Oceanview Resort & Spa",
    description:
      "A luxurious beachfront resort offering stunning ocean views, a full-service spa, " +
      "infinity pool, and fine dining. Perfect for romantic getaways and family vacations " +
      "with direct beach access and water sports.",
  },
  {
    name: "Mountain Lodge Retreat",
    description:
      "A cozy mountain lodge nestled in the pine forests with hiking trails, a stone " +
      "fireplace lounge, and farm-to-table restaurant. Ideal for nature lovers seeking " +
      "a peaceful escape with skiing and snowboarding nearby.",
  },
  {
    name: "Downtown City Hotel",
    description:
      "A modern boutique hotel in the heart of the city, walking distance to museums, " +
      "theaters, and shopping districts. Features a rooftop bar, business center, and " +
      "contemporary rooms with skyline views.",
  },
  {
    name: "Desert Oasis Inn",
    description:
      "A unique desert retreat with adobe-style architecture, stargazing terrace, and " +
      "cactus gardens. Offers guided desert tours, a refreshing pool, and southwestern " +
      "cuisine in a tranquil setting.",
  },
  {
    name: "Lakeside Cabin Village",
    description:
      "Rustic yet comfortable lakeside cabins surrounded by forest. Enjoy kayaking, " +
      "fishing, campfire evenings, and a general store. A family-friendly destination " +
      "for outdoor adventures and relaxation by the water.",
  },
];

// ---------------------------------------------------------------------------
// Azure SQL helpers (tedious)
// ---------------------------------------------------------------------------
function connectToSql(
  server: string,
  database: string,
  credential: DefaultAzureCredential
): Promise<Connection> {
  return new Promise((resolve, reject) => {
    const config = {
      server,
      authentication: {
        type: "azure-active-directory-access-token" as const,
        options: {
          token: "", // set dynamically below
        },
      },
      options: {
        database,
        encrypt: true,
        port: 1433,
        rowCollectionOnDone: true,
        rowCollectionOnRequestCompletion: true,
      },
    };

    // Acquire a token for Azure SQL
    credential
      .getToken("https://database.windows.net/.default")
      .then((tokenResponse: AccessToken) => {
        config.authentication.options.token = tokenResponse.token;
        const connection = new Connection(config);

        connection.on("connect", (err) => {
          if (err) {
            reject(err);
          } else {
            resolve(connection);
          }
        });

        connection.on("error", reject);
        connection.connect();
      })
      .catch(reject);
  });
}

function executeSql(
  connection: Connection,
  sql: string,
  parameters?: Array<{ name: string; type: unknown; value: unknown }>
): Promise<Record<string, unknown>[]> {
  return new Promise((resolve, reject) => {
    const rows: Record<string, unknown>[] = [];
    const request = new Request(sql, (err, _rowCount, resultRows) => {
      if (err) {
        reject(err);
        return;
      }
      // Build rows from column metadata
      if (resultRows) {
        for (const row of resultRows) {
          const obj: Record<string, unknown> = {};
          for (const col of row) {
            obj[col.metadata.colName] = col.value;
          }
          rows.push(obj);
        }
      }
      resolve(rows);
    });

    if (parameters) {
      for (const p of parameters) {
        request.addParameter(p.name, p.type as any, p.value);
      }
    }

    connection.execSql(request);
  });
}

// ---------------------------------------------------------------------------
// Azure OpenAI helper
// ---------------------------------------------------------------------------
async function generateEmbeddings(
  client: AzureOpenAI,
  deployment: string,
  texts: string[]
): Promise<number[][]> {
  const response = await client.embeddings.create({
    model: deployment,
    input: texts,
  });
  return response.data.map((item) => item.embedding);
}

// Converts a number[] embedding to the JSON-array string format that
// Azure SQL's VECTOR type accepts, e.g. "[0.123,0.456,...]"
function vectorToString(embedding: number[]): string {
  return "[" + embedding.join(",") + "]";
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main(): Promise<void> {
  console.log("=== Azure SQL Vector Search — TypeScript Quickstart ===\n");

  // 1. Load configuration
  const config = loadConfig();
  console.log(`Server:     ${config.azureSqlServer}`);
  console.log(`Database:   ${config.azureSqlDatabase}`);
  console.log(`OpenAI:     ${config.azureOpenAiEndpoint}`);
  console.log(`Deployment: ${config.azureOpenAiEmbeddingDeployment}\n`);

  // 2. Authenticate with DefaultAzureCredential (used for both SQL and OpenAI)
  const credential = new DefaultAzureCredential();

  // 3. Connect to Azure SQL
  console.log("Connecting to Azure SQL Database...");
  const connection = connectToSql(
    config.azureSqlServer,
    config.azureSqlDatabase,
    credential
  );
  const conn = await connection;
  console.log("Connected.\n");

  // 4. Create the hotels table with a VECTOR(1536) column
  console.log("Creating hotels table (if not exists)...");
  await executeSql(
    conn,
    `IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'hotels_typescript')
     BEGIN
       CREATE TABLE dbo.hotels_typescript (
         id INT IDENTITY(1,1) PRIMARY KEY,
         name NVARCHAR(200) NOT NULL,
         description NVARCHAR(MAX) NOT NULL,
         embedding VECTOR(1536) NULL
       );
     END`
  );
  console.log("Table ready.\n");

  // 5. Generate embeddings with Azure OpenAI
  console.log("Generating embeddings with Azure OpenAI...");
  const azureADTokenProvider = getBearerTokenProvider(
    credential,
    "https://cognitiveservices.azure.com/.default"
  );
  const openaiClient = new AzureOpenAI({
    endpoint: config.azureOpenAiEndpoint,
    azureADTokenProvider,
    apiVersion: "2024-10-21",
  });

  const descriptions = hotels.map((h) => h.description);
  const embeddings = await generateEmbeddings(
    openaiClient,
    config.azureOpenAiEmbeddingDeployment,
    descriptions
  );
  console.log(`Generated ${embeddings.length} embeddings (dimension: ${embeddings[0].length}).\n`);

  // 6. Insert sample data
  console.log("Inserting hotel data with embeddings...");

  // Clear previous run data
  await executeSql(conn, "DELETE FROM dbo.hotels_typescript");

  for (let i = 0; i < hotels.length; i++) {
    const hotel = hotels[i];
    const embeddingStr = vectorToString(embeddings[i]);
    await executeSql(
      conn,
      `INSERT INTO dbo.hotels_typescript (name, description, embedding)
       VALUES (@name, @description, CAST(@embedding AS VECTOR(1536)))`,
      [
        { name: "name", type: TYPES.NVarChar, value: hotel.name },
        { name: "description", type: TYPES.NVarChar, value: hotel.description },
        { name: "embedding", type: TYPES.NVarChar, value: embeddingStr },
      ]
    );
    console.log(`  Inserted: ${hotel.name}`);
  }
  console.log();

  // 7. Perform vector similarity search
  const searchQuery = "luxury beachfront hotel with ocean views and spa";
  console.log(`Searching for: "${searchQuery}"\n`);

  const queryEmbeddings = await generateEmbeddings(
    openaiClient,
    config.azureOpenAiEmbeddingDeployment,
    [searchQuery]
  );
  const queryVectorStr = vectorToString(queryEmbeddings[0]);

  const results = await executeSql(
    conn,
    `SELECT TOP 3
       name,
       description,
       VECTOR_DISTANCE('cosine', embedding, CAST(@queryVector AS VECTOR(1536))) AS distance
     FROM dbo.hotels_typescript
     ORDER BY distance`,
    [
      {
        name: "queryVector",
        type: TYPES.NVarChar,
        value: queryVectorStr,
      },
    ]
  );

  // 8. Display results
  console.log("--- Search Results (Top 3 by Cosine Distance) ---\n");
  for (const row of results) {
    const distance = Number(row["distance"]);
    const similarity = (1 - distance).toFixed(4);
    console.log(`  Hotel:       ${row["name"]}`);
    console.log(`  Description: ${(row["description"] as string).substring(0, 100)}...`);
    console.log(`  Distance:    ${distance.toFixed(4)}`);
    console.log(`  Similarity:  ${similarity}`);
    console.log();
  }

  // Cleanup: close connection
  conn.close();
  console.log("Done. Connection closed.");
}

main().catch((err) => {
  console.error("Error:", err);
  process.exit(1);
});
