"""Few-shot product recognition: propose -> embed -> match -> fuse.

The v3 till used two closed-set YOLO classifiers, so it could only ever know the
twelve products they were trained on and could never say "I do not know".  This
package replaces that with a class-agnostic proposer, an embedding model and a
gallery of reference vectors, so a new product is added by showing it to the
camera instead of by collecting a dataset and retraining.
"""
