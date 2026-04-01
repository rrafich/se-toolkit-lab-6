#!/usr/bin/env python3
"""Regression tests for the agent."""

import json
import subprocess
import sys


def test_agent_basic_question():
    """Test that agent returns valid JSON with required fields."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be a list"
    assert output["answer"], "Answer is empty"
    
    print("✓ Test passed: basic question")


def test_agent_documentation_question():
    """Test that agent uses read_file tool for documentation questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What are the steps to protect a branch on GitHub?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert "source" in output, "Missing 'source' field"
    
    # Check that tools were used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected tool calls for documentation question"
    
    # Check that read_file was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"Expected read_file tool, got: {tools_used}"
    
    # Check answer is not empty
    assert output["answer"], "Answer is empty"
    
    print("✓ Test passed: documentation question")


def test_agent_list_files():
    """Test that agent uses list_files tool for directory listing questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What files are in the wiki directory?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that list_files was used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected tool calls for listing question"
    
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "list_files" in tools_used, f"Expected list_files tool, got: {tools_used}"
    
    print("✓ Test passed: list_files question")


def test_agent_merge_conflict():
    """Test that agent uses read_file tool for merge conflict questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert "source" in output, "Missing 'source' field"
    
    # Check that tools were used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected tool calls for merge conflict question"
    
    # Check that read_file was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"Expected read_file tool, got: {tools_used}"
    
    # Check source contains git-related file
    source = output["source"].lower()
    assert "git" in source, f"Expected git-related source, got: {output['source']}"
    
    # Check answer is not empty
    assert output["answer"], "Answer is empty"
    
    print("✓ Test passed: merge conflict question")


def test_agent_git_workflow():
    """Test that agent can answer questions about Git workflow."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What is the Git workflow for creating a task branch?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert "source" in output, "Missing 'source' field"
    
    # Check that tools were used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected tool calls for Git workflow question"
    
    # Check that read_file was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"Expected read_file tool, got: {tools_used}"
    
    # Check answer is not empty
    assert output["answer"], "Answer is empty"
    
    print("✓ Test passed: Git workflow question")


if __name__ == "__main__":
    test_agent_basic_question()


def test_agent_security_path_traversal():
    """Test that agent blocks path traversal attempts."""
    result = subprocess.run(
        [sys.executable, "agent.py", "Read the file ../../etc/passwd"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that tool calls contain error messages about path traversal
    tool_calls = output["tool_calls"]
    if len(tool_calls) > 0:
        # At least one tool call should have an error about invalid path
        path_errors = [
            tc for tc in tool_calls 
            if tc.get("result", {}).get("error") and 
            ("path traversal" in tc["result"]["error"].lower() or 
             "outside project" in tc["result"]["error"].lower())
        ]
        assert len(path_errors) > 0, f"Expected path traversal error, got: {tool_calls}"
    
    print("✓ Test passed: security path traversal")


def test_agent_docker_compose_question():
    """Test that agent can answer questions about docker-compose configuration."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What is the purpose of docker-compose.yml in this project?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert "source" in output, "Missing 'source' field"
    
    # Check that tools were used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected tool calls for docker-compose question"
    
    # Check that read_file was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"Expected read_file tool, got: {tools_used}"
    
    # Check answer is not empty
    assert output["answer"], "Answer is empty"
    
    # Check source references docker-compose file
    source = output["source"]
    assert "docker" in source.lower(), f"Expected docker-related source, got: {source}"
    
    print("✓ Test passed: docker-compose question")


if __name__ == "__main__":
    test_agent_basic_question()
    test_agent_documentation_question()
    test_agent_list_files()
    test_agent_merge_conflict()
    test_agent_git_workflow()
    test_agent_security_path_traversal()
    test_agent_docker_compose_question()
    print("\nAll 7 tests passed!")
