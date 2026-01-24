#!/usr/bin/env python3
"""
Age, Gender and Emotion Prediction System

This script combines MiVOLO (age and gender prediction) with ResEmoteNet (emotion recognition)
to provide comprehensive facial analysis from images.

Author: AI Assistant
Date: July 2025
"""

import argparse
import cv2
import torch
import sys
import os
import numpy as np
import torch.nn.functional as F
import torchvision.transforms as transforms
from PIL import Image
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from mivolo.model.yolo_detector import Detector
from mivolo.model.mi_volo import MiVOLO
from resemotenet.ResEmoteNet import ResEmoteNet


class AgeGenderEmotionPredictor:
    """Main predictor class for age, gender and emotion recognition"""
    
    def __init__(self, device="cuda:0", 
                 detector_path="models/yolov8x_person_face.pt",
                 mivolo_path="models/model_imdb_cross_person_4.22_99.46.pth.tar",
                 resemotenet_path="models/affectnet7_model.pth"):
        """
        Initialize the predictor with model paths
        
        Args:
            device (str): Device for computation (cuda:0 or cpu)
            detector_path (str): Path to YOLOv8 face detector
            mivolo_path (str): Path to MiVOLO model weights
            resemotenet_path (str): Path to ResEmoteNet model weights
        """
        self.device = self._validate_device(device)
        self.detector_path = detector_path
        self.mivolo_path = mivolo_path
        self.resemotenet_path = resemotenet_path
        
        # Emotion mapping for consistent output
        self.emotion_mapping = {
            'Neutral': 'neutral',
            'Happy': 'happy',
            'Sad': 'sad',
            'Surprised': 'surprise',
            'Fear': 'fear',
            'Disgusted': 'disgust',
            'Angry': 'angry'
        }
        
        # Load models
        self._load_models()
    
    def _validate_device(self, device):
        """Validate and set appropriate device"""
        if device.startswith("cuda") and not torch.cuda.is_available():
            print(f"Warning: {device} not available, switching to CPU.", file=sys.stderr)
            return "cpu"
        return device
    
    def _load_models(self):
        """Load all required models"""
        try:
            # Load face detector
            self.detector = Detector(self.detector_path, self.device)
            
            # Load MiVOLO model
            self.mivolo_model = MiVOLO(
                self.mivolo_path, 
                self.device, 
                half=True, 
                use_persons=True, 
                disable_faces=False
            )
            
            # Load ResEmoteNet model
            self.resemotenet_model = self._load_resemotenet()
            
        except Exception as e:
            print(f"Error loading models: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _load_resemotenet(self):
        """Load ResEmoteNet model for emotion recognition"""
        try:
            model = ResEmoteNet().to(self.device)
            
            if not os.path.exists(self.resemotenet_path):
                raise FileNotFoundError(f"ResEmoteNet model not found at {self.resemotenet_path}")
            
            checkpoint = torch.load(self.resemotenet_path, weights_only=False)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.eval()
            return model
            
        except Exception as e:
            print(f"Error loading ResEmoteNet model: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _predict_emotion(self, face_roi):
        """Predict emotion using ResEmoteNet on face ROI"""
        emotions = ['Neutral', 'Happy', 'Sad', 'Surprised', 'Fear', 'Disgusted', 'Angry']
        
        transform = transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.Grayscale(num_output_channels=3),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        
        try:
            # Convert BGR to RGB for PIL
            face_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(face_rgb)
            
            # Apply transforms
            img_tensor = transform(pil_image).unsqueeze(0).to(self.device)
            
            # Inference
            with torch.no_grad():
                outputs = self.resemotenet_model(img_tensor)
                probabilities = F.softmax(outputs, dim=1)
            
            scores = probabilities.cpu().numpy().flatten()
            max_index = np.argmax(scores)
            emotion = emotions[max_index]
            
            return self.emotion_mapping.get(emotion, emotion.lower())
            
        except Exception as e:
            print(f"Error in emotion prediction: {e}", file=sys.stderr)
            return 'neutral'  # Default fallback
    
    def predict(self, image_path):
        """
        Predict age, gender and emotion from image
        
        Args:
            image_path (str): Path to input image
            
        Returns:
            dict: Dictionary containing age, gender and emotion predictions
        """
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot load image '{image_path}'!")
        
        # Detect faces
        detections = self.detector.predict(img)
        face_inds = detections.get_bboxes_inds("face")
        
        if not face_inds:
            raise ValueError("No face detected in the image.")
        
        # Predict age and gender with MiVOLO
        self.mivolo_model.predict(img, detections)
        
        # Get first detected face
        idx = face_inds[0]
        x1, y1, x2, y2 = detections.get_bbox_by_ind(idx)
        age = detections.ages[idx]
        gender = detections.genders[idx]
        
        # Extract face ROI for emotion prediction
        face_roi = img[y1:y2, x1:x2]
        
        if face_roi.size == 0:
            raise ValueError("Invalid face region detected.")
        
        # Predict emotion
        emotion = self._predict_emotion(face_roi)
        
        # Format gender for Czech output
        gender_cz = "muž" if gender == "male" else "žena" if gender == "female" else str(gender)
        
        return {
            'age': int(round(age)),
            'gender': gender_cz,
            'emotion': emotion,
            'bbox': (x1, y1, x2, y2)
        }


def main():
    """Main function for command line interface"""
    parser = argparse.ArgumentParser(
        description="Age, Gender and Emotion Prediction System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python predict.py image.jpg
    python predict.py image.jpg --device cpu
    python predict.py image.jpg --detector custom_detector.pt
        """
    )
    
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--detector", "-d", 
                        default="models/yolov8x_person_face.pt",
                        help="YOLOv8 face detector (.pt)")
    parser.add_argument("--mivolo", "-m",
                        default="models/model_imdb_cross_person_4.22_99.46.pth.tar",
                        help="MiVOLO model weights (.pth.tar)")
    parser.add_argument("--resemotenet", "-r",
                        default="models/affectnet7_model.pth",
                        help="ResEmoteNet model weights (.pth)")
    parser.add_argument("--device", 
                        default="cuda:0",
                        help="Device for computation (cuda:0 or cpu)")
    parser.add_argument("--verbose", "-v", 
                        action="store_true",
                        help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        # Initialize predictor
        if args.verbose:
            print("Initializing models...", file=sys.stderr)
        
        predictor = AgeGenderEmotionPredictor(
            device=args.device,
            detector_path=args.detector,
            mivolo_path=args.mivolo,
            resemotenet_path=args.resemotenet
        )
        
        # Make prediction
        if args.verbose:
            print(f"Processing image: {args.image}", file=sys.stderr)
        
        result = predictor.predict(args.image)
        
        # Output result
        if args.verbose:
            print(f"Age: {result['age']}")
            print(f"Gender: {result['gender']}")
            print(f"Emotion: {result['emotion']}")
            print(f"Face bbox: {result['bbox']}")
        else:
            print(f"{result['age']}, {result['gender']}, {result['emotion']}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
