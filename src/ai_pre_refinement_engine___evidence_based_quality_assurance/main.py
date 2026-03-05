#!/usr/bin/env python
import sys
from ai_pre_refinement_engine___evidence_based_quality_assurance.crew import AiPreRefinementEngineEvidenceBasedQualityAssuranceCrew

# This main file is intended to be a way for your to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    # Accept feature_idea from CLI: python main.py run "your feature description"
    feature_idea = sys.argv[2] if len(sys.argv) > 2 else 'sample_value'

    inputs = {
        'feature_idea': feature_idea,
    }
    print(f"Starting crew with feature_idea: {feature_idea}")
    AiPreRefinementEngineEvidenceBasedQualityAssuranceCrew().crew().kickoff(inputs=inputs)


def run_with_trigger(inputs=None):
    """Run the crew with provided inputs (used by deployment triggers and chat)."""
    if inputs is None:
        inputs = {'feature_idea': 'sample_value'}
    AiPreRefinementEngineEvidenceBasedQualityAssuranceCrew().crew().kickoff(inputs=inputs)


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        'feature_idea': sys.argv[4] if len(sys.argv) > 4 else 'sample_value',
    }
    try:
        AiPreRefinementEngineEvidenceBasedQualityAssuranceCrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        AiPreRefinementEngineEvidenceBasedQualityAssuranceCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        'feature_idea': sys.argv[4] if len(sys.argv) > 4 else 'sample_value',
    }
    try:
        AiPreRefinementEngineEvidenceBasedQualityAssuranceCrew().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: main.py <command> [<args>]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "run":
        run()
    elif command == "train":
        train()
    elif command == "replay":
        replay()
    elif command == "test":
        test()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
