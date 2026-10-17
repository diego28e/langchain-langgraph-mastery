"""Fine-tuning decisions for Module 14: the ticket-router dataset, numpy baselines, metrics and recorded predictions.

Introduced in Lesson 14.03 (when to fine-tune) and used by 14.04 (QLoRA on Colab) and Project 14. Pure Python
plus numpy: nothing here trains a neural network or calls a model; training happens on Colab (14.04).
"""
from mastery.finetune.baselines import LogReg, NaiveBayes, featurize
from mastery.finetune.llm_router import RouterRun, fewshot_prompt, pick_examples, route_with_llm
from mastery.finetune.metrics import (RoutePoint, accuracy, best_threshold, calibration, confusion, correct_map,
                                      expected_calibration_error, macro_f1, route_curve, top_confusions)
from mastery.finetune.predictions import RECORDED_DIR, load_predictions, save_predictions
from mastery.finetune.tickets import (QUEUE_HELP, QUEUES, SYSTEM_PROMPT, TICKETS_PATH, assign_splits, by_split,
                                      family_overlap, load_tickets, to_chat_example, write_chat_jsonl)

__all__ = ["RouterRun", "fewshot_prompt", "pick_examples", "route_with_llm", "LogReg", "NaiveBayes", "featurize", "RoutePoint", "accuracy", "best_threshold", "calibration", "confusion",
           "correct_map", "expected_calibration_error", "macro_f1", "route_curve", "top_confusions", "RECORDED_DIR",
           "load_predictions", "save_predictions", "QUEUE_HELP", "QUEUES", "SYSTEM_PROMPT", "TICKETS_PATH",
           "assign_splits", "by_split", "family_overlap", "load_tickets", "to_chat_example", "write_chat_jsonl"]
