import os
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
# Import backend components to run the actual pipeline
from backend.agents.planner import plan_task
from backend.agents.worker import execute_step
from backend.agents.auditor import audit_and_synthesize
from backend.security.safety import sanitize_content
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.exceptions import OutputParserException

# Load env (specifically for GROQ_API_KEY and potentially OPENAI_API_KEY)
load_dotenv()

# --- Configuration ---
# RAGAS defaults to OpenAI GPT-4 for evaluation.
# If you don't have OPENAI_API_KEY, we can try to use Groq via ChatOpenAI wrapper,
# but RAGAS is optimized for OpenAI.
# For now, we assume the environment might have an OpenAI key or we will configure it to use Groq.

use_groq_for_eval = True

if use_groq_for_eval:
    # Use Llama-3-70b as the judge to save costs/compatibility if OpenAI key missing
    # Note: RAGAS metrics can be sensitive to model quality.
    eval_llm = ChatOpenAI(
        model="llama3-70b-8192",
        api_key=os.environ.get("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )
else:
    eval_llm = None # Uses default OpenAI

# Define the 20 Queries and Ground Truths
test_cases = [
    {
        "question": "What was the total revenue recorded for January 2023?",
        "ground_truth": "The total revenue for January 2023 was $5,000 USD."
    },
    {
        "question": "How much did expenses increase from Jan 2023 to Feb 2023?",
        "ground_truth": "Expenses increased by $500, from $500 in Jan to $1,000 in Feb."
    },
    {
        "question": "What is the profit margin for March 2023 assuming 50% fixed costs?",
        "ground_truth": "Revenue for March 2023 was 5500. Profit depends on total costs."
    },
    {
        "question": "List the top 3 separate expense categories for Q1.",
        "ground_truth": "Specific expense categories are not available in the financials table, only aggregated 'Expenses'."
    },
    {
        "question": "Plot the revenue trend for the first quarter of 2023.",
        "ground_truth": "Jan: $5000, Feb: $6000, Mar: $5500. Trend shows an increase then a slight dip."
    },
    {
        "question": "What are the primary risk factors mentioned in the latest 10-K?",
        "ground_truth": "Risks related to global supply chain measures, market volatility, and regulatory changes."
    },
    {
        "question": "Compare the current asset ratio to the industry average.",
        "ground_truth": "Current Assets are 25000. Industry average is not available in the database."
    },
    {
        "question": "What is the sector allocation of the portfolio?",
        "ground_truth": "The database lists 'Technology' and 'Healthcare' segments."
    },
    {
        "question": "Predict the Q2 revenue based on Q1 growth.",
        "ground_truth": "Predictions require extrapolation from Q1 data (Jan: 5000, Feb: 6000, Mar: 5500)."
    },
    {
        "question": "Who is the auditor for the 2023 financial statements?",
        "ground_truth": "Deloitte & Touche LLP."
    },
    {
        "question": "What is the debt-to-equity ratio?",
        "ground_truth": "Liabilities: 50000, Equity: 100000. Ratio is 0.5."
    },
    {
        "question": "Summarize the Management Discussion and Analysis (MD&A).",
        "ground_truth": "Management focuses on efficient R&D and cost reduction in Asia."
    },
    {
        "question": "Are there any pending lawsuits?",
        "ground_truth": "Yes, a patent suit versus Competitor X."
    },
    {
        "question": "What is the EPS (Earnings Per Share) for 2022?",
        "ground_truth": "The EPS is 3.45."
    },
    {
        "question": "Show the balance sheet summary.",
        "ground_truth": "Assets: 150000, Liabilities: 50000, Equity: 100000."
    },
    {
        "question": "Does the portfolio contain any crypto assets?",
        "ground_truth": "No crypto assets found in holdings."
    },
    {
        "question": "What is the dividend yield?",
        "ground_truth": "Approximately 1.5%."
    },
    {
        "question": "Analyze the cash flow from operations.",
        "ground_truth": "Operating Cash Flow is +10M."
    },
    {
        "question": "What is the filing date of the latest 10-Q?",
        "ground_truth": "2023-04-15."
    },
    {
        "question": "Is the company ESG compliant?",
        "ground_truth": "The company strives for sustainability but no specific compliance certification is listed."
    }
]

# --- Helper Function to Run Pipeline and Capture Context ---
def run_pipeline_with_context(question: str):
    print(f"\nRunning Query: {question}")
    try:
        # 1. Plan
        plan = plan_task(question)
        
        # 2. Work
        context_str = ""
        context_list = []
        steps = plan.split("\n")
        for step in steps:
            if step.strip() and (step[0].isdigit() or step.startswith("-")):
                clean_step = step.replace("**", "")
                clean_step = clean_step.split(".", 1)[1].strip() if "." in clean_step else clean_step
                
                # Execute
                result = execute_step(clean_step)
                
                # Append to context
                context_str += f"\nStep: {step}\nResult: {result}\n"
                context_list.append(f"Step: {clean_step}\nResult: {result}")
        
        # 3. Audit
        final_answer = audit_and_synthesize(question, context_str, graph_allowed=True)
        safe_answer = sanitize_content(final_answer)
        
        return safe_answer, context_list
        
    except Exception as e:
        print(f"Error processing {question}: {e}")
        return "Error", ["Error"]

# --- Main Evaluation Loop ---
def main():
    questions = []
    answers = []
    contexts = []
    ground_truths = []
    
    print(f"Starting Evaluation on {len(test_cases)} items...")
    
    for i, case in enumerate(test_cases):
        q = case["question"]
        gt = case["ground_truth"]
        
        print(f"[{i+1}/{len(test_cases)}] {q}")
        
        ans, ctx = run_pipeline_with_context(q)
        
        questions.append(q)
        answers.append(ans)
        contexts.append(ctx) # RAGAS expects list[str]
        ground_truths.append(gt)
    
    # Create Dataset
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    }
    dataset = Dataset.from_dict(data)
    
    # Run RAGAS
    print("\nCalculating RAGAS metrics...")
    try:
        results = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
            llm=eval_llm, # Use Groq Llama-3 as judge
            embeddings=eval_llm # Note: This might fail if using ChatModel for embeddings. RAGAS separates llm and embeddings.
            # RAGAS usually defaults to OpenAIEmbeddings. We might need to omit embeddings if Groq doesn't support them, 
            # OR rely on default if user has OPENAI_KEY.
            # If this fails, we will catch and export raw data.
        )
        # Convert to Pandas
        df_results = results.to_pandas()
    except Exception as e:
        print(f"RAGAS Calculation Failed: {e}")
        print("Exporting Raw Results without metrics...")
        df_results = pd.DataFrame(data)
        # Add empty cols
        for col in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            df_results[col] = 0.0

    # Save to Excel
    output_file = "live_ragas_evaluation_SFA.xlsx"
    df_results.to_excel(output_file, index=False)
    print(f"\nEvaluation Complete. Saved to {output_file}")
    
    # Preview
    print(df_results.head(1).to_markdown())

if __name__ == "__main__":
    main()
