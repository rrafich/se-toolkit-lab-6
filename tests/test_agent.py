#!/usr/bin/env python3
"""Regression tests for the agent."""

import json
import subprocess
import sys


def test_agent_basic_question():
    """Test that agent returns valid JSON with required fields."""
    # Run the agent
    result = subprocess.run(https://github.com/rrafich/se-toolkit-lab-6/pull/2/conflict?name=plans%252Ftask-1.md&base_oid=b36dcd89448cc8d0c08f52aef1209b0b3982ecb0&head_oid=049dcd4dccb086e3cdfd0710ef1348895f3d5acf
        [sys.executable, "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    # Parse JSON output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be a list"
    
    # Check answer is not empty
    assert output["answer"], "Answer is empty"
    
    print("✓ Test passed: basic question")


if __name__ == "__main__":
    test_agent_basic_question()
    print("All tests passed!")
