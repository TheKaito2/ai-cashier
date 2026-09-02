#!/usr/bin/env python3
"""Generate the stand-in camera frames: a demo frame with two products on the
mat, and the same mat empty.  The till's --demo replays the first; --self-test
(and CI, on the frozen build) calibrates on the second and scans the first.

    python docs/tools/make_demo_frame.py docs/assets/demo_frame.jpg docs/assets/demo_mat.png
"""
import sys, numpy as np, cv2

w, h = 1280, 720


def mat():
    img = np.zeros((h, w, 3), np.uint8)
    for y in range(h):                              # soft vertical gradient = counter surface
        img[y, :] = (38 + y * 26 // h, 42 + y * 28 // h, 48 + y * 30 // h)
    cv2.putText(img, "DEMO FRAME - no webcam attached", (150, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (170, 180, 190), 2)
    return img


def bag(img, x, y, bw, bh, colour, label, sub):
    cv2.rectangle(img, (x, y), (x + bw, y + bh), colour, -1)
    cv2.rectangle(img, (x, y), (x + bw, y + bh), (255, 255, 255), 2)
    cv2.rectangle(img, (x + 10, y + 12), (x + bw - 10, y + 46), (255, 255, 255), -1)
    cv2.putText(img, label, (x + 18, y + 38), cv2.FONT_HERSHEY_DUPLEX, 0.75, colour, 2)
    cv2.putText(img, sub, (x + 14, y + bh - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


empty = mat()
frame = mat()
bag(frame, 150, 190, 320, 380, (30, 130, 220), "LAY'S", "Flat Original 75g")
bag(frame, 560, 190, 320, 380, (40, 150, 70), "TASTO", "Japanese Seaweed 68g")
cv2.imwrite(sys.argv[1], frame)
if len(sys.argv) > 2:
    cv2.imwrite(sys.argv[2], empty)
print("wrote", *sys.argv[1:])
