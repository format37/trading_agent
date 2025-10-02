import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ToolUseBlock
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

async def main():
    """Demonstrate Claude SDK using Python code execution for CSV analysis."""

    # Configure options to allow Python code execution
    options = ClaudeAgentOptions(
        allowed_tools=["mcp__ide__executeCode", "Read", "mcp__polygon__polygon_news"],
        permission_mode="bypassPermissions",  # Full permissions - no prompts
        cwd=os.getcwd(),
        mcp_servers={
            "polygon": {
                "type": "http",
                "url": "http://localhost:8009/polygon/"
            }
        }
    )

    print("=" * 60)
    print("Claude SDK Python Analysis Demo")
    print("=" * 60)
    print("\nAsking Claude to analyze the CSV using Python code execution...\n")

    async with ClaudeSDKClient(options=options) as client:
        # Prompt that explicitly requests Python code execution
        prompt = """Please do the following:

1. Call the polygon news tool
2. Read the response
3. Tell me how many rows it has (excluding header)
4. Find the mean value in the 'datetime' column
5. Find a row with the longest text in the 'topic' column"""

        await client.query(prompt)

        # Process the response
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}\n")
                    elif isinstance(block, ToolUseBlock):
                        if block.name == "mcp__ide__executeCode":
                            print(f"[Executing Python code]")
                            print(f"Code:\n{block.input.get('code', '')}\n")

    print("=" * 60)
    print("Analysis complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
