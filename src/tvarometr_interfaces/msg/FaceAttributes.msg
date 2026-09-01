# One face analysis pass. Labels are the model's own English ones - the Czech
# wording the robot writes on the board is produced further down the line, so
# this message stays language neutral.
int32 age
string gender               # "male" / "female"
string emotion              # "neutral", "happy", "sad", ...
float32 emotion_confidence  # softmax score of the reported emotion, 0..1

# Where the face sat in the frame. Feeds the approach move later on: how big the
# face is and where it sits vertically is what tells the robot how far away and
# how high the person is.
sensor_msgs/RegionOfInterest face_bbox
uint32 image_width
uint32 image_height
