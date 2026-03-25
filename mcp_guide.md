# Using HireScope via MCP (Model Context Protocol)

You can now use HireScope's job intelligence tools directly inside **Claude Desktop**, **Cursor**, or any other MCP-compliant client. This allows you to analyze jobs without leaving your AI chat environment.

## 🛠️ Provided Tools

1.  **`analyze_job`**: Takes a job URL and returns a full intelligence report (JD, Company, Salary).
2.  **`get_glassdoor_rating`**: Returns a company's rating, review count, and pros/cons.
3.  **`search_vault`**: Searches your local historical database for previously analyzed jobs.

---

## ⚙️ Configuration (Claude Desktop)

To use HireScope in Claude Desktop, add the following to your `claude_desktop_config.json`:

> [!TIP]
> On macOS, this file is typically at: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hirescope": {
      "command": "python",
      "args": [
        "/Users/yeshwanth/Desktop/Github/HireScope/backend/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/Users/yeshwanth/Desktop/Github/HireScope/backend",
        "GEMINI_API_KEY": "insert_your_key",
        "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:5433/hirescope"
      }
    }
  }
}
```

> [!IMPORTANT]
> Ensure the paths above match your actual project location. You can copy the environment variables from your `.env` file.

---

## 🧪 Testing the Server

You can test the MCP server manually using the MCP Inspector:

```bash
cd backend
npx @modelcontextprotocol/inspector python mcp_server.py
```

This will open a web interface where you can trigger the `analyze_job` tool and see the output.
