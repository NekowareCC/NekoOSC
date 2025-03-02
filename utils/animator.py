import os
import time
import xml.etree.ElementTree as ET
from typing import List, Union, Dict, Optional


class AnimatorError(Exception):
    """Custom exception for animation-related errors."""
    pass


class Frame:
    def __init__(self, frame: Dict[str, Union[str, int]], format_type: str):
        self.text: Optional[str] = frame.get("text", "").strip()
        self.duration: Optional[int] = frame.get("duration") if format_type == "duration" else None
        self.percentage: Optional[int] = frame.get("percentage") if format_type == "percentage" else None


class Animation:
    def __init__(self, animation_type: str, name: str, frames: List[Dict[str, Union[str, int]]]):
        self.type = animation_type
        self.name = name
        self.frames = [Frame(frame, animation_type) for frame in frames]
        self._current_frame_index = 0
        self.last_updated = time.time()
        self.duration = len(self.frames) - 1

    def __str__(self):
        return f"{self.type, self.name, self.frames, self.duration}"

    @property
    def current_frame(self) -> Frame:
        return self.frames[self._current_frame_index]

    def next_frame(self, percentage: int = 0) -> Frame:
        """Advance to the next frame if the percentage reaches or exceeds the frame's percentage."""
        if self.type == "duration":
            if time.time() - self.last_updated >= self.current_frame.duration / 1000:
                self._current_frame_index = (self._current_frame_index + 1) % len(self.frames)
                self.last_updated = time.time()
        elif self.type == "percentage":
            closest_frame_index = 0
            closest_percentage_diff = float('inf')
            found = False

            for i in range(len(self.frames)):
                frame_percentage = self.frames[i].percentage
                if frame_percentage <= percentage:
                    found = True
                    percentage_diff = percentage - frame_percentage
                    if percentage_diff < closest_percentage_diff:
                        closest_percentage_diff = percentage_diff
                        closest_frame_index = i

            if not found:
                self._current_frame_index = 0
            else:
                self._current_frame_index = closest_frame_index

        return self.current_frame


class NekoAnimator:
    def __init__(self, animator_path: str = "./"):
        self.animator_path = animator_path
        self.animation_list: List[Animation] = []
        self.preview_list: List[Animation] = []
        self.load_animations()

    def load_animations(self):
        self.animation_list = []
        self.preview_list = []
        os.makedirs(self.animator_path, exist_ok=True)
        for file in os.listdir(self.animator_path):
            if file.endswith(".xml"):
                self._load_animation(file)

    def _load_animation(self, animation_name: str):
        animation_path = os.path.join(self.animator_path, animation_name)
        try:
            tree = ET.parse(animation_path)
            root = tree.getroot()

            if root.tag != "animation":
                raise AnimatorError("The root element must be <animation>.")

            format_type = root.get("format")
            if format_type not in ["duration", "percentage"]:
                raise AnimatorError("Invalid animation format. Must be 'duration' or 'percentage'.")

            frames = []
            for frame in root.findall("frame"):
                frame_data = {
                    "text": frame.text.strip() if frame.text else "",
                    format_type: int(frame.attrib.get(format_type, 0))
                }
                frames.append(frame_data)

            animation = Animation(format_type, animation_name[:-4], frames)
            self.animation_list.append(animation)
            self._preview_animation(animation)
        except Exception as e:
            raise AnimatorError(f"Failed to load animation {animation_name}: {e}")

    def new_animation(self, animation: Animation) -> Animation:
        counter = 1
        for anim in self.animation_list:
            if animation.name in anim.name:
                counter += 1
        animation_path = os.path.join(self.animator_path, f"{animation.name}.xml")
        try:
            tree = ET.parse(animation_path)
            root = tree.getroot()

            if root.tag != "animation":
                raise AnimatorError("The root element must be <animation>.")

            format_type = root.get("format")
            if format_type not in ["duration", "percentage"]:
                raise AnimatorError("Invalid animation format. Must be 'duration' or 'percentage'.")

            frames = []
            for frame in root.findall("frame"):
                frame_data = {
                    "text": frame.text.strip() if frame.text else "",
                    format_type: int(frame.attrib.get(format_type, 0))
                }
                frames.append(frame_data)

            animation = Animation(format_type, animation.name + str(counter), frames)
            self.animation_list.append(animation)
            return animation
        except Exception as e:
            raise AnimatorError(f"Failed to load animation {animation.name}: {e}")

    def _preview_animation(self, animation: Animation) -> Animation:
        animation_path = os.path.join(self.animator_path, f"{animation.name}.xml")
        try:
            tree = ET.parse(animation_path)
            root = tree.getroot()

            if root.tag != "animation":
                raise AnimatorError("The root element must be <animation>.")

            format_type = root.get("format")
            if format_type not in ["duration", "percentage"]:
                raise AnimatorError("Invalid animation format. Must be 'duration' or 'percentage'.")

            frames = []
            for frame in root.findall("frame"):
                frame_data = {
                    "text": frame.text.strip() if frame.text else "",
                    format_type: int(frame.attrib.get(format_type, 0))
                }
                frames.append(frame_data)

            new_animation = Animation(format_type, f"{animation.name} Preview", frames)
            self.preview_list.append(new_animation)
            return new_animation
        except Exception as e:
            raise AnimatorError(f"Failed to load animation {animation.name}: {e}")


def play_animation(animation: Animation):
    """Continuously plays an animation by printing each frame."""
    while True:
        frame = animation.next_frame()
        print(f"Frame {animation._current_frame_index}: {frame.text}")
        time.sleep(0.5)


def main():
    nekopath = os.path.join(os.getenv("LOCALAPPDATA", ""), "Nekoware", "NekoOSC", "animator")
    animator = NekoAnimator()

    if animator.animation_list:
        for animation in animator.animation_list:
            play_animation(animation)
    else:
        print("No animations found.")


if __name__ == "__main__":
    main()
