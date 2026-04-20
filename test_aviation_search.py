import asyncio
import sys
import os

# Add the current directory to path so we can import server
sys.path.insert(0, os.path.dirname(__file__))

from server import run_aviation_api_search

async def test_aviation_search():
    print("Testing run_aviation_api_search (planning mode)...")
    try:
        result = await run_aviation_api_search(test_mode=True)
        print("Success!")
        print(f"Report date: {result.get('report_date')}")
        print(f"Period: {result.get('period')}")
        print(f"Triggers to check: {result.get('triggers_to_check')}")
        print(f"Execution order: {result.get('execution_order')}")

        tool_calls = result.get('recommended_tool_calls', [])
        print(f"Recommended tool calls: {len(tool_calls)}")
        for i, call in enumerate(tool_calls, 1):
            print(f"{i}. {call['tool']}: {call['description']}")
            print(f"   Parameters: {call['parameters']}")

        print("Test completed successfully!")
        return result

    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_aviation_search())