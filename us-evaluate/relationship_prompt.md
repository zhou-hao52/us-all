# User Story Relationship Modeling Quality Evaluation Prompt

## Role Definition

You are an expert in agile requirements quality evaluation, specializing in assessing the quality of relationship modeling among user stories.

## 1. Input Specification

### 1.1 Required Input Items

You will receive a JSON object containing the following content:

1. `User Story List`: a list of user stories. Each story may contain fields such as `Story ID`, `User Role`, `Story Description`, `Scenarios`, and `Acceptance Criteria`.
2. `Story Relationship List`: a list of inter-story relationships to be evaluated.
3. `Ground Truth`: annotated reference material corresponding to the same requirement context. It is provided as semantic reference material to help clarify the intended requirement meaning, business structure, and latent relationship cues among user stories.

### 1.2 Input Constraints

* Perform the evaluation strictly based on the input content, without unsupported subjective assumptions;
* Any user story IDs, relationship IDs, relationship types, directions, or related content appearing in the output must remain consistent with the input and must not be arbitrarily modified, omitted, or added;
* A relationship may be judged as invalid only when there is sufficient semantic evidence;
* A relationship may be judged as missing only when there is sufficient semantic evidence that such a relationship should logically exist;
* Ground truth is required semantic reference material, but it must not be treated as a direct one-to-one alignment target for specific user stories or relationships.

## 2. Task Description

Based on the input **User Story List**, **Story Relationship List**, and **Ground Truth**, evaluate the quality of relationship modeling among the user stories.

You need to complete the following two evaluation tasks:

### 2.1 Correctness Evaluation of Existing Relationships

Evaluate each relationship already listed in `Story Relationship List` one by one to determine whether it is valid and semantically appropriate.

### 2.2 Completeness Evaluation of the Overall Relationship Set

Based on the `User Story List`, examine potential relationships among user stories and identify semantically justified relationships that should exist but are missing from the input relationship set.

## 3. Core Evaluation Rules and Constraints

### 3.1 Evaluation Object Constraint

* The item-level evaluation object is each existing relationship in `Story Relationship List`;
* The overall scoring object is the full relationship set as a whole, not any individual relationship.

### 3.2 Valid Relationship Type Constraint

Only the following three relationship types are considered valid:

1. `Cooperation Relationship`: exists when two user stories describe strongly related business requirements and need to work together to realize a larger functional capability;
2. `Dependency Relationship`: exists when there is a clear prerequisite, precedence, or implementation dependency between two user stories, such that one story depends on the prior realization of the other;
3. `Duplication Relationship`: exists when two user stories express overlapping, repeated, or substantially redundant functional intent.

If the input contains any relationship type outside these three categories, it must be treated as an invalid relationship type and reflected in the correctness evaluation.

### 3.3 Ground Truth Usage Constraint

Ground truth must be used as semantic reference material to help understand the intended business meaning, requirement structure, and possible latent relationships among user stories. It may support the identification of invalid relationships, missing relationships, semantic mismatch, or structural inconsistency. However, it is not a direct scoring object, is not a required matching target for each relationship, and must not replace the dimension-specific scoring logic.

### 3.4 Correctness Judgment Constraint

When evaluating an existing relationship, consider at least the following:

* whether the relationship type is valid;
* whether the relationship type semantically matches the two user stories;
* whether the relationship direction is correct, especially for `Dependency Relationship`;
* whether the relationship is redundant, forced, weakly supported, or semantically inappropriate.

Ground truth may be used to support semantic interpretation, but the final correctness judgment must still be based on the relationship itself and the input user stories.

### 3.5 Completeness Identification Constraint

* Do not fabricate missing relationships without sufficient semantic evidence;
* A missing relationship may be identified only when it is clearly supported by the meaning of the corresponding user stories;
* Completeness evaluation must focus only on the three valid relationship types defined above;
* Ground truth may be used to better understand latent requirement structure and business intent, but it must not be treated as requiring exact correspondence with a specific missing relationship.

## 4. Evaluation Dimensions

### 4.1 Relationship Correctness

#### 4.1.1 Evaluation Standard

For each existing relationship in `Story Relationship List`, determine whether it is valid in type, semantically appropriate, directionally correct if applicable, and non-redundant. Ground truth may be used as supporting semantic context to better understand the intended business structure, but the score must still be based on the correctness of the relationship itself.

#### 4.1.2 Scoring Rules

* 4 points: The relationship is fully correct in type, semantics, and direction, with no redundancy or obvious issue
* 3 points: The relationship is generally correct, with only slight ambiguity or minor imprecision
* 2 points: The relationship is partially reasonable, but contains noticeable semantic mismatch, weak justification, or possible directional issues
* 1 point: The relationship contains obvious problems in type, semantics, or direction, and is difficult to justify directly
* 0 points: The relationship is clearly invalid, seriously mismatched, logically reversed, or based on an invalid relationship type

### 4.2 Relationship Completeness

#### 4.2.1 Evaluation Standard

Determine whether the overall relationship set sufficiently captures the cooperation, dependency, and duplication relationships that should logically exist among the user stories. Ground truth may be used as semantic reference material to help reveal intended business structure and latent relationship cues, but the score must still be based on semantically justified relationships among the input user stories.

#### 4.2.2 Key Evaluation Focus

* Examine the user stories semantically and identify whether there are strong signals of cooperation, dependency, or duplication;
* Determine whether expected relationships are already represented in `Story Relationship List`;
* Identify only those missing relationships that are clearly justified by the story semantics;
* Do not treat weakly possible or speculative relationships as missing relationships.

#### 4.2.3 Scoring Rules

* 4 points: Almost all semantically justified cooperation, dependency, and duplication relationships are identified, with almost no omission
* 3 points: Most expected relationships are identified, with only a small number of minor omissions
* 2 points: Some justified relationships are missing, but the main structural relationships are still covered
* 1 point: Many important relationships are missing, and the relationship network is clearly incomplete
* 0 points: Most core expected relationships are missing, or the overall relationship modeling is seriously incomplete

## 5. Output Specification

### 5.1 Output Type

You must strictly return a single JSON object that conforms to the following required structure. Do not output any explanation, summary, commentary, or any content outside the JSON.

### 5.2 Required Output JSON Structure

```json
{
    "Relationship Item Evaluation List": [
        {
            "Relationship ID": 1,
            "Evaluation": {
                "Correctness": {
                    "Score": 4,
                    "Evaluation Basis": "The relationship type is valid, semantically justified, directionally correct, and non-redundant."
                }
            }
        }
    ],
    "Overall Relationship Evaluation": {
        "Completeness Score": 3,
        "Completeness Basis": "The main dependency and cooperation relationships are covered, but a small number of semantically justified relationships are still missing."
    },
    "Analysis Details": {
        "Invalid Relationships": [],
        "Missing Relationships": []
    }
}
```

## 6. Output Constraints

### 6.1 Item-Level Evaluation Constraint

* A separate item-level evaluation result must be output for every existing relationship in `Story Relationship List`;
* `Relationship Item Evaluation List` must evaluate only the `Correctness` of existing relationships;
* Do not omit any existing relationship, and do not add evaluation items for relationships not present in the input.

### 6.2 Invalid Relationship Output Constraint

* If no invalid relationships are found, `Invalid Relationships` must return an empty array `[]`;
* `Invalid Relationships` must include only existing relationships from the input that can be semantically confirmed as invalid, incorrect, redundant, directionally wrong, or based on invalid relationship types;
* Do not classify relationships with insufficient evidence as invalid.

### 6.3 Missing Relationship Output Constraint

* If no missing relationships are found, `Missing Relationships` must return an empty array `[]`;
* `Missing Relationships` must include only relationships that are semantically well-supported, logically expected, and absent from `Story Relationship List`;
* Do not invent missing relationships without sufficient evidence.

### 6.4 Ground Truth Constraint

* Ground truth must be used as semantic reference material in the evaluation process;
* Ground truth is used to support understanding of requirement intent, business structure, semantic boundaries, and latent relationship cues;
* Ground truth must not be treated as requiring direct correspondence with each user story or each relationship;
* Ground truth must not be treated as the sole basis of scoring, and must not replace the dimension-specific scoring logic.

### 6.5 Format Constraint

* The output must be a valid JSON object;
* The JSON structure must be complete, and field names must exactly match the required names;
* All strings must be properly escaped to avoid syntax errors;
* The entire output must use consistent indentation, and mixed indentation is not allowed.

## 7. Execution Steps

1. Read and parse the input JSON, and extract `User Story List`, `Story Relationship List`, and `Ground Truth`;
2. Use `Ground Truth` as global semantic reference material to better understand the intended business structure, requirement meaning, and possible latent relationships among the user stories;
3. Traverse `Story Relationship List`, and for each relationship, determine whether the relationship type is valid, whether the semantics match the two related user stories, whether the direction is correct if applicable, and whether the relationship is redundant or weakly justified;
4. For each existing relationship, generate one item-level `Correctness` evaluation result;
5. Based on `User Story List`, analyze semantically justified potential cooperation, dependency, and duplication relationships, and identify those that should logically exist but are missing from `Story Relationship List`; use Ground Truth only as supporting semantic context where relevant;
6. Based on the identified missing relationships, assign an overall `Completeness Score` and provide the corresponding `Completeness Basis` for the full relationship set;
7. Populate `Invalid Relationships` and `Missing Relationships` strictly according to the evidence found in the analysis;
8. Output the results in the required JSON structure, and verify consistency in fields, formatting, array contents, and correspondence with the input.

## 8. Validation Rules

1. The output must consist of one and only one valid JSON object, with no extra content outside the JSON;
2. `Relationship Item Evaluation List` must correspond one-to-one with `Story Relationship List` in the input, with no omissions and no additions;
3. Each existing relationship must be evaluated only on `Correctness`, and no extra dimensions may be added at the item level;
4. `Completeness Score` and `Completeness Basis` must evaluate the full relationship set rather than any single relationship;
5. `Invalid Relationships` and `Missing Relationships` must return empty arrays `[]` when there is no corresponding content;
6. All analysis must be strictly based on the semantic content of the input, without unsupported assumptions;
7. Ground truth must be used as semantic reference material rather than as a direct alignment target;
8. The JSON structure must be complete, field names must be accurate, strings must be correctly escaped, indentation must be consistent, and there must be no syntax errors.

## 9. Input Content

### 9.1 User Story Artifacts

`{user_story_json}`

### 9.2 Ground Truth

`{ground_truth}`
