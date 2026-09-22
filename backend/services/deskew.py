import cv2
import numpy as np
import logging
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class MultiAngleDeskewNormalizer:
    def __init__(
        self,
        enabled: bool = True,
        min_angle_threshold: float = 0.5,    # Do not transform nearly straight pages (<0.5 deg)
        max_skew_angle: float = 45.0,        # Angles >45 deg indicate orthogonal rotation
        min_confidence: float = 0.40         # Minimum confidence required to apply correction
    ):
        self.enabled = enabled
        self.min_angle_threshold = min_angle_threshold
        self.max_skew_angle = max_skew_angle
        self.min_confidence = min_confidence

    def estimate_skew(self, image_np: np.ndarray) -> Dict[str, Any]:
        """
        Estimates orthogonal rotation and fine skew angle using OpenCV Hough lines
        and minAreaRect analysis.
        Returns a dict:
        {
            "orthogonal_angle": 0 | 90 | 180 | 270,
            "skew_angle": float (-45.0 to +45.0),
            "total_angle": float,
            "confidence": float (0.0 to 1.0),
            "should_correct": bool,
            "reason": str
        }
        """
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_np.copy()

        h, w = gray.shape

        max_dim = 1500
        scale = 1.0
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            resized = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            resized = gray

        _, thresh = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Detect lines with morphological structure
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        lines = cv2.HoughLinesP(dilated, 1, np.pi / 180, threshold=100, minLineLength=50, maxLineGap=20)

        angles = []
        if lines is not None and len(lines) > 0:
            for line in lines:
                coords = line.flatten()
                if len(coords) < 4:
                    continue
                x1, y1, x2, y2 = coords[:4]
                dx = float(x2 - x1)
                dy = float(y2 - y1)
                if dx == 0:
                    continue
                angle_deg = float(np.degrees(np.arctan2(dy, dx)))
                if -45.0 <= angle_deg <= 45.0:
                    angles.append(angle_deg)

        if not angles:
            contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contour_angles = []
            for cnt in contours:
                if cv2.contourArea(cnt) > 200:
                    rect = cv2.minAreaRect(cnt)
                    angle = rect[-1]
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle
                    if abs(angle) <= 45.0:
                        contour_angles.append(angle)
            if len(contour_angles) >= 5:
                angles = contour_angles

        if not angles or len(angles) < 3:
            return {
                "orthogonal_angle": 0,
                "skew_angle": 0.0,
                "total_angle": 0.0,
                "confidence": 0.0,
                "should_correct": False,
                "reason": "insufficient_lines_for_confidence"
            }

        median_angle = float(np.median(angles))
        std_dev = float(np.std(angles))
        confidence = float(np.clip(1.0 - (std_dev / 5.0), 0.0, 1.0))

        abs_angle = abs(median_angle)
        if abs_angle < self.min_angle_threshold:
            return {
                "orthogonal_angle": 0,
                "skew_angle": median_angle,
                "total_angle": median_angle,
                "confidence": confidence,
                "should_correct": False,
                "reason": f"angle_below_threshold_{abs_angle:.2f}deg"
            }

        if confidence < self.min_confidence:
            return {
                "orthogonal_angle": 0,
                "skew_angle": median_angle,
                "total_angle": median_angle,
                "confidence": confidence,
                "should_correct": False,
                "reason": f"confidence_too_low_{confidence:.2f}"
            }

        return {
            "orthogonal_angle": 0,
            "skew_angle": median_angle,
            "total_angle": median_angle,
            "confidence": confidence,
            "should_correct": True,
            "reason": f"deskew_approved_{median_angle:.2f}deg"
        }

    def deskew_image(
        self,
        image_np: np.ndarray,
        angle: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Rotates image around its center to counteract skew.
        Preserves complete geometric transformation matrix M (2x3)
        and computes inverse transformation matrix M_inv (2x3).
        """
        h, w = image_np.shape[:2]
        center = (w / 2.0, h / 2.0)

        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        M_inv = cv2.invertAffineTransform(M)

        straightened = cv2.warpAffine(
            image_np,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )

        return straightened, M, M_inv

    @staticmethod
    def transform_points(pts: np.ndarray, M: np.ndarray) -> np.ndarray:
        """
        Applies 2x3 affine matrix M to N points of shape (N, 2).
        Returns transformed points of shape (N, 2).
        """
        homo_pts = np.hstack([pts, np.ones((len(pts), 1), dtype=np.float64)]) # (N, 3)
        transformed = np.dot(M, homo_pts.T).T # (N, 2)
        return transformed

    @staticmethod
    def transform_bbox_forward(
        bbox: List[float],
        M: np.ndarray,
        img_w: float,
        img_h: float
    ) -> List[float]:
        """Transforms a bounding box [x0, y0, x1, y1] through affine matrix M"""
        x0, y0, x1, y1 = bbox
        corners = np.array([
            [x0, y0],
            [x1, y0],
            [x1, y1],
            [x0, y1]
        ], dtype=np.float64)

        t_corners = MultiAngleDeskewNormalizer.transform_points(corners, M)
        tx0 = float(np.min(t_corners[:, 0]))
        ty0 = float(np.min(t_corners[:, 1]))
        tx1 = float(np.max(t_corners[:, 0]))
        ty1 = float(np.max(t_corners[:, 1]))

        return [
            max(0.0, tx0),
            max(0.0, ty0),
            min(img_w, tx1),
            min(img_h, ty1)
        ]

    @staticmethod
    def transform_bbox_inverse(
        bbox: List[float],
        M_inv: np.ndarray,
        img_w: float,
        img_h: float
    ) -> List[float]:
        """Inversely transforms a bounding box back to original coordinates"""
        return MultiAngleDeskewNormalizer.transform_bbox_forward(bbox, M_inv, img_w, img_h)

deskew_normalizer = MultiAngleDeskewNormalizer()
