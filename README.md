# IoT User Story Generator and Evaluator

## Project Overview

This project is a comprehensive toolset for generating and evaluating high-quality user stories for IoT systems. It leverages Large Language Models (LLMs) to transform raw IoT requirements into structured user stories, scenarios, acceptance criteria, and story relationships, while also providing a robust evaluation framework to assess the quality of these artifacts.

## Directory Structure

```
us-all/
├── requirement/
│   └── requirements.json       # Contains 261 IoT user requirements
├── us-evaluate/                # User story evaluation tools
│   ├── Acceptance Criteria_prompt.md
│   ├── Scenarios_prompt.md
│   ├── US_prompt.md
│   ├── relationship_prompt.md
│   └── run_evaluation.py
└── us-generate/                # User story generation tools
    ├── US_generate_prompt.md
    └── llm_requests.py
```

## Key Components

### 1. Requirement Management

The `requirements.json` file contains 261 detailed IoT system requirements, each with:
- Unique ID
- Initial demand description
- Detailed demand specifications

These requirements cover a wide range of IoT applications including smart agriculture, industrial monitoring, healthcare, smart cities, and more.

### 2. User Story Generation

The `us-generate` module uses LLMs to convert raw requirements into structured user story artifacts:

- **User Roles**: Identifies relevant user roles for each requirement
- **User Stories**: Generates standardized user stories in the format "As a [User Role], I want [Function] so that [Business Value]"
- **Scenarios**: Creates test scenarios in Given-When-Then format for each user story
- **Acceptance Criteria**: Defines clear, testable conditions for each user story
- **Story Relationships**: Identifies logical relationships between user stories (Cooperation, Dependency, Duplication)

### 3. User Story Evaluation

The `us-evaluate` module assesses the quality of generated user story artifacts across multiple dimensions:

- **User Story Quality**: Evaluates independence, negotiability, business value, estimability, granularity, testability, and overall demand coverage
- **Scenario Quality**: Assesses correctness and faithfulness of scenarios
- **Acceptance Criteria Quality**: Evaluates correctness, verifiability, and faithfulness of acceptance criteria
- **Relationship Quality**: Analyzes correctness and completeness of story relationships

## How It Works

### User Story Generation Process

1. **Input Requirements**: The system reads requirements from `requirements.json`
2. **Prompt Construction**: Uses `US_generate_prompt.md` to construct prompts for the LLM
3. **LLM Processing**: Sends requests to the LLM API (DashScope) to generate user story artifacts
4. **Output Generation**: Saves generated user stories, scenarios, acceptance criteria, and relationships as JSON files

### User Story Evaluation Process

1. **Input Artifacts**: Reads generated user story artifacts and ground truth data
2. **Prompt Construction**: Uses evaluation prompt templates to construct assessment prompts
3. **LLM Processing**: Sends requests to the LLM API to evaluate artifact quality
4. **Results Analysis**: Collects and summarizes evaluation results for each artifact

## Getting Started

### Prerequisites

- Python 3.7+
- API key for DashScope (or compatible OpenAI API endpoint)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd us-all
   ```

2. Install required dependencies:
   ```bash
   pip install requests
   ```

### Configuration

1. Update API keys in the following files:
   - `us-generate/llm_requests.py`: Set your DashScope API keys in the `API_KEYS` list
   - `us-evaluate/run_evaluation.py`: Set your DashScope API keys in the `DEFAULT_API_KEYS` list

### Usage

#### Generating User Stories

1. Navigate to the `us-generate` directory:
   ```bash
   cd us-generate
   ```

2. Run the generation script:
   ```bash
   python llm_requests.py
   ```

3. Generated user stories will be saved in the `response/iot_tasks` directory

#### Evaluating User Stories

1. Navigate to the `us-evaluate` directory:
   ```bash
   cd us-evaluate
   ```

2. Run the evaluation script:
   ```bash
   python run_evaluation.py --root ../
   ```

3. Evaluation results will be saved in the `output` directory

## Output Format

### Generated User Story Artifacts

```json
{
    "User Roles": ["Role1", "Role2", ...],
    "User Story List": [
        {
            "Story ID": 1,
            "User Role": "Role",
            "Story Description": "As a ...",
            "Scenarios": [
                "scenario ...: Given ...; When ...; Then ..."
            ],
            "Acceptance Criteria": [
                "Criterion 1",
                "Criterion 2"
            ]
        }
    ],
    "Story Relationship List": [
        {
            "Relationship ID": 1,
            "Source Story ID": 1,
            "Target Story ID": 2,
            "Relationship Type": "Cooperation/Dependency/Duplication Relationship",
            "Relationship Description": "Brief explanation"
        }
    ]
}
```

### Evaluation Results

The evaluation produces JSON files with scores and detailed rationales for each quality dimension, such as:

- User story quality scores (Independence, Negotiability, Business Value, etc.)
- Scenario quality scores (Correctness, Faithfulness)
- Acceptance criteria quality scores (Correctness, Verifiability, Faithfulness)
- Relationship quality scores (Correctness, Completeness)

## Use Cases

1. **Requirement Engineering**: Transform high-level IoT requirements into structured user stories
2. **Quality Assurance**: Evaluate the quality of user stories before development
3. **Agile Development**: Provide well-structured user stories for sprint planning
4. **Requirements Analysis**: Identify gaps and improvements in existing requirements
5. **Educational Purposes**: Learn best practices for writing high-quality user stories

## Benefits

- **Automation**: Reduces manual effort in creating and evaluating user stories
- **Consistency**: Ensures standardized format and quality across all user stories
- **Scalability**: Handles large volumes of requirements efficiently
- **Quality Improvement**: Provides objective evaluation to identify areas for improvement
- **Time Savings**: Accelerates the requirements engineering process

## Technologies Used

- **Python**: Core scripting language
- **LLM API**: DashScope (Aliyun) for natural language processing
- **JSON**: Data interchange format for requirements and results
- **Asynchronous Programming**: For efficient API calls and parallel processing

## Contributing

Contributions to this project are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Contact

For questions or support, please contact the project maintainer.
