import time
from dataclasses import dataclass, asdict
from typing import List, Dict

from jiwer import wer, cer


@dataclass
class BenchmarkResult:
    model_name: str
    word_error_rate: float
    char_error_rate: float
    inference_time_seconds: float
    transcript_length: int

    def to_dict(self):
        return asdict(self)


class BenchmarkEvaluator:
    """
    Evaluates transcription quality across different providers.

    Metrics:
    - WER (Word Error Rate)
    - CER (Character Error Rate)
    - Inference latency
    """

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    def evaluate(
        self,
        model_name: str,
        predicted_transcript: str,
        ground_truth: str,
        inference_time: float,
    ) -> BenchmarkResult:
        """
        Compare predicted transcript against ground truth.
        """

        word_error = wer(ground_truth, predicted_transcript)
        char_error = cer(ground_truth, predicted_transcript)

        result = BenchmarkResult(
            model_name=model_name,
            word_error_rate=word_error,
            char_error_rate=char_error,
            inference_time_seconds=inference_time,
            transcript_length=len(predicted_transcript.split()),
        )

        self.results.append(result)
        return result

    def compare_models(self) -> List[Dict]:
        """
        Return benchmark results sorted by WER.
        Lower WER is better.
        """

        sorted_results = sorted(
            self.results,
            key=lambda x: x.word_error_rate
        )

        return [r.to_dict() for r in sorted_results]

    def print_summary(self):
        print("\n=== BENCHMARK SUMMARY ===\n")

        ranked = self.compare_models()

        for idx, result in enumerate(ranked, start=1):
            print(f"#{idx} {result['model_name']}")
            print(f"   WER: {result['word_error_rate']:.4f}")
            print(f"   CER: {result['char_error_rate']:.4f}")
            print(f"   Time: {result['inference_time_seconds']:.2f}s")
            print()


# -------------------------------------------------
# Example usage
# -------------------------------------------------

if __name__ == "__main__":
    evaluator = BenchmarkEvaluator()

    ground_truth = (
        "Rahul will send the API keys tomorrow and "
        "Sarah will finish payment integration by Friday"
    )

    assemblyai_prediction = (
        "Rahul will send the API keys tomorrow and "
        "Sarah will finish the payment integration by Friday"
    )

    whisper_prediction = (
        "Rahul sends API keys tomorrow and "
        "Sarah finishes payment integration Friday"
    )

    evaluator.evaluate(
        model_name="AssemblyAI",
        predicted_transcript=assemblyai_prediction,
        ground_truth=ground_truth,
        inference_time=2.31,
    )

    evaluator.evaluate(
        model_name="Whisper Large-v3",
        predicted_transcript=whisper_prediction,
        ground_truth=ground_truth,
        inference_time=5.84,
    )

    evaluator.print_summary()