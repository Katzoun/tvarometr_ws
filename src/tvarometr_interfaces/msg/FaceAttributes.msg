# One face analysis. Labels are the models' English; the Czech comes later.
int32 age
string gender               # "male" / "female"
string emotion              # "neutral", "happy", "sad", ...
float32 emotion_confidence  # softmax score of the reported emotion, 0..1

# Where the face sat in the frame.
sensor_msgs/RegionOfInterest face_bbox
uint32 image_width
uint32 image_height
