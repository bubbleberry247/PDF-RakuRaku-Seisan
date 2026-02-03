# Plan: QuestionBank Excel Population

## Current
- 13 text files extracted from past exam PDFs (R5/R6/R7, AM/PM, answers)
- QuestionBank Excel has 28 columns, 0 data rows
- Answer data: R5 from text file, R6/R7 from Excel

## Problem
- Text files need parsing into structured rows
- Answer data in different formats needs merging
- Duplicate files exist (R6 English/Japanese versions)

## Target
- QuestionBank sheet populated with ~216 questions (72 x 3 years)
- Unnecessary sheets deleted

## Change: Python script `build_question_bank.py`

### Step 1: Parse all answer data into dict[year][qnum] = answer
### Step 2: Parse 6 question text files (skip duplicates)
### Step 3: Map to 28 QuestionBank columns
### Step 4: Write to Excel, delete unnecessary sheets

## Verification
- Row count = 216
- Spot-check answers: R7-No.1=2, R5-No.1=3, R6-No.1=3
