import re
import os
import shutil
from pathlib import Path

block_heading_pattern = re.compile(r'^(#{1,6}) (.+)$')  # h
block_unordered_list_pattern = re.compile(r'^- (.*)$')  # ul
block_ordered_list_pattern = re.compile(r'^\d+. (.*)$') # ol
block_quote_pattern = re.compile(r'^> ?(.*)$')           # quote
block_code_pattern = re.compile(r'^```')                # code
                                                        # p
                                                        # empty

inline_bold_pattern = re.compile(r"\*\*([^*]+[^*]*[^*]|[^*])\*\*")
inline_italic_pattern = re.compile(r"\_([^_]+[^_]*[^_]|[^_])\_")
inline_link_pattern = re.compile(r"(?<!!)\[(.*?)\]\((.*?)\)")
inline_image_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
inline_code_pattern = re.compile(r"\`([^`]+[^`]*[^`]|[^`])\`")

class Block:
    def __init__(self, block_type=None):
        self.block_type = block_type
        self.content = []

    def inline_filters(self, line):
        line = re.sub(inline_bold_pattern, r"<b>\1</b>", line)
        line = re.sub(inline_italic_pattern, r"<i>\1</i>", line)
        line = re.sub(inline_link_pattern, r'<a href="\2">\1</a>', line)
        line = re.sub(inline_image_pattern, r'<img src="\2" alt="\1" />', line)
        line = re.sub(inline_code_pattern, r"<code>\1</code>", line)
        return line

    def consume_line(self, line):
        if self.block_type == "h":
            match_ = re.match(block_heading_pattern, line)
            num_hashtags, title = match_.groups()
            self.num_hashtags = len(num_hashtags)
            self.content.append(title)
            return

        if self.block_type == "ul":
            match_ = re.match(block_unordered_list_pattern, line)
            (text,) = match_.groups()
            text = self.inline_filters(text)
            self.content.append(text)
            return
        
        if self.block_type == "ol":
            match_ = re.match(block_ordered_list_pattern, line)
            (text,) = match_.groups()
            text = self.inline_filters(text)
            self.content.append(text)
            return

        if self.block_type == "quote":
            match_ = re.match(block_quote_pattern, line)
            (text,) = match_.groups()
            text = self.inline_filters(text)
            self.content.append(text)
            return

        if self.block_type == "code":
            if not re.match(block_code_pattern, line):
                self.content.append(line)
            return
        
        if self.block_type == "p":
            self.content.append(self.inline_filters(line))
            return

    def render(self):
        if len(self.content) == 0:
            return ""

        if self.block_type == "h":
            return f"<h{self.num_hashtags}>" + " ".join(self.content) + f"</h{self.num_hashtags}>"

        if self.block_type == "ul":
            return "<ul>\n" + "\n".join(["\t<li>" + text + "</li>" for text in self.content]) + "\n</ul>"
        
        if self.block_type == "ol":
            return "<ol>\n" + "\n".join(["\t<li>" + text + "</li>" for text in self.content]) + "\n</ol>"

        if self.block_type == "quote":
            return "<quote>\n" + "<br>\n".join(self.content) + "\n</quote>"

        if self.block_type == "code":
            return "<code>\n" + "<br>\n".join(self.content) + "\n</code>"
        
        if self.block_type == "p":
            return "<p>\n" + " ".join(self.content) + "\n</p>"

    def __repr__(self) -> str:
        return " ".join(self.content)[:100]

class StateMachine:
    def __init__(self):
        self.current_state = None
        self.current_block = Block()
        self.blocks = []
        self.null_block = Block()

    def finish(self):
        if len(self.current_block.content) > 0:
            self.blocks.append(self.current_block)

    # Returns the correct Block for the line
    def transition(self, pattern):
        
        assert pattern in ["empty", "h", "ul", "ol", "quote", "code", "p"]

        if self.current_state is None:
            if pattern == "empty":
                return self.null_block
            self.current_state = pattern
            self.current_block.block_type = pattern
            return self.current_block

        elif pattern == "empty" and self.current_state != "code":
            # New Block is coming
            self.blocks.append(self.current_block)
            self.current_block = Block()
            self.current_state = None
            return self.null_block

        elif self.current_state == "h":
            if pattern in ["h", "ul", "ol", "quote", "code", "p"]:
                # New block
                self.blocks.append(self.current_block)
                self.current_block = Block(pattern)
                self.current_state = pattern
                return self.current_block

        elif self.current_state == "ul":
            if pattern in ["h", "ol", "quote", "code", "p"]:
                # New block
                self.blocks.append(self.current_block)
                self.current_block = Block(pattern)
                self.current_state = pattern
                return self.current_block
            elif pattern == "ul":
                # Same block
                return self.current_block

        elif self.current_state == "ol":
            if pattern in ["h", "ul", "quote", "code", "p"]:
                # New block
                self.blocks.append(self.current_block)
                self.current_block = Block(pattern)
                self.current_state = pattern
                return self.current_block
            elif pattern == "ol":
                # Same block
                return self.current_block
        
        elif self.current_state == "quote":
            if pattern in ["h", "ul", "ol", "code", "p"]:
                # New block
                self.blocks.append(self.current_block)
                self.current_block = Block(pattern)
                self.current_state = pattern
                return self.current_block
            elif pattern == "quote":
                # Same block
                return self.current_block
        
        elif self.current_state == "code":
            if pattern == "code":
                # This code block is finished
                self.blocks.append(self.current_block)
                self.current_block = Block()
                self.current_state = None
                return self.blocks[-1]
            else:
                # Same block
                return self.current_block
        
        elif self.current_state == "p":
            if pattern in ["h", "ul", "ol", "quote", "code"]:
                # New block
                self.blocks.append(self.current_block)
                self.current_block = Block(pattern)
                self.current_state = pattern
                return self.current_block
            elif pattern == "p":
                # Same p block
                return self.current_block
        
        raise NotImplementedError(f"somehow nothing did match: current_state {self.current_state}, pattern {pattern}, current_block_type {self.current_block.block_type}")

def main():
    # Delete everything in public/
    target = Path("public")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    # Copy from static/ to public/
    static = Path("static")
    if static.exists():
        shutil.copytree(static, target, dirs_exist_ok=True)

    # Find all markdown files
    files = []
    for path in Path("content").rglob("*"):
        if path.is_file() and path.suffix == ".md":
            files.append(str(path))

    print(files)
    
    # Generate general Template
    with open("template.html", "r") as f:
        template = f.read()

    title_pattern = re.compile(r"{{ Title }}")
    content_pattern = re.compile(r"{{ Content }}")

    for file in files:
        dest = Path(os.path.join("public", file[8:-3]+".html"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Generating page from {file} to {dest}")

        with open(file, "r") as f:
            lines = f.readlines()

        statemachine = StateMachine()

        for line in lines:
            line = line.strip("\n")
            # Check what patterns match
            pattern = None
            if line == "":
                pattern = "empty"
            elif re.match(block_heading_pattern, line):
                pattern = "h"
            elif re.match(block_unordered_list_pattern, line):
                pattern = "ul"
            elif re.match(block_ordered_list_pattern, line):
                pattern = "ol"
            elif re.match(block_quote_pattern, line):
                pattern = "quote"
            elif re.match(block_code_pattern, line):
                pattern = "code"
            else:
                pattern = "p"

            # Get correct block to consume line
            block = statemachine.transition(pattern)
            block.consume_line(line)
        statemachine.finish()

        # Get title
        title = None
        for block in statemachine.blocks:
            if hasattr(block, "num_hashtags") and block.num_hashtags == 1:
                title = block.content[0].strip()
                break

        # replace parts in template
        content = "\n".join([block.render() for block in statemachine.blocks])
        
        final = re.sub(title_pattern, title, template)
        final = re.sub(content_pattern, content, final)

        with open(dest, "w") as f:
            f.write(final)

if __name__ == "__main__":
    main()