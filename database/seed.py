from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Problem

DEMO_PROBLEMS = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "summary": "Find two values in an array that add up to a target.",
        "difficulty": "Easy",
        "topics": ["Arrays", "Hash Maps"],
        "examples": [
            {"input": "nums = [2, 7, 11, 15], target = 9", "output": "[0, 1]", "explanation": "2 + 7 = 9."},
        ],
        "constraints": "Each input has exactly one solution, and the same element cannot be used twice.",
        "starter_code": {
            "javascript": "function twoSum(nums, target) {\n  return [];\n}\n",
            "python": "def two_sum(nums, target):\n    return []\n",
        },
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "summary": "Determine whether brackets in a string are correctly nested.",
        "difficulty": "Easy",
        "topics": ["Stack", "Strings"],
        "examples": [
            {"input": "s = '()[]{}'", "output": "true", "explanation": "Every opening bracket has a matching closing bracket."},
        ],
        "constraints": "The input contains only '(', ')', '{', '}', '[' and ']'.",
        "starter_code": {
            "javascript": "function isValid(s) {\n  return false;\n}\n",
            "python": "def is_valid(s):\n    return False\n",
        },
    },
    {
        "slug": "merge-intervals",
        "title": "Merge Intervals",
        "summary": "Merge overlapping intervals into a minimal set of intervals.",
        "difficulty": "Medium",
        "topics": ["Arrays", "Sorting", "Intervals"],
        "examples": [
            {
                "input": "intervals = [[1, 3], [2, 6], [8, 10]]",
                "output": "[[1, 6], [8, 10]]",
                "explanation": "The first two intervals overlap and can be combined.",
            },
        ],
        "constraints": "Intervals are sorted by start time and do not contain invalid endpoints.",
        "starter_code": {
            "javascript": "function merge(intervals) {\n  return [];\n}\n",
            "python": "def merge(intervals):\n    return []\n",
        },
    },
    {
        "slug": "binary-search",
        "title": "Binary Search",
        "summary": "Search a sorted array for a target in logarithmic time.",
        "difficulty": "Easy",
        "topics": ["Arrays", "Binary Search"],
        "examples": [
            {"input": "nums = [-1, 0, 3, 5, 9, 12], target = 9", "output": "4", "explanation": "The target is at index 4."},
        ],
        "constraints": "nums is sorted in ascending order and contains unique values.",
        "starter_code": {
            "javascript": "function search(nums, target) {\n  return -1;\n}\n",
            "python": "def search(nums, target):\n    return -1\n",
        },
    },
]


def seed_demo_data(session: Session) -> None:
    existing_slugs = set(session.scalars(select(Problem.slug)).all())
    for problem_data in DEMO_PROBLEMS:
        if problem_data["slug"] not in existing_slugs:
            session.add(Problem(**problem_data))
    session.commit()
