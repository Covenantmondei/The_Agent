import os
from openai import OpenAI
import dotenv
from datetime import datetime

dotenv.load_dotenv()

client = OpenAI(api_key="anything", base_url="http://localhost:12434/engines/llama.cpp/v1")


class ChatGPTTerminal:

    def __init__(self):
        self.client = client
        self.model = "ai/llama3.2:1B-Q4_0"
        self.conversation_history = []
        self.system_prompt = "You are a helpful, friendly, and knowledgeable AI assistant."

    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        """Print application header"""
        print("=" * 70)
        print(" " * 20 + "ChatGPT Terminal Chat")
        print("=" * 70)
        print(f"Model: {self.model}")
        print(f"Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 70)
        print("Commands:")
        print("  /clear    - Clear conversation history")
        print("  /history  - Show conversation history")
        print("  /system   - Change system prompt")
        print("  /model    - Change model")
        print("  /exit     - Exit the application")
        print("=" * 70)
        print()

    def send_message(self, user_message: str, stream: bool = True) -> str:

        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Prepare messages with system prompt
        messages = [
            {"role": "system", "content": self.system_prompt}
        ] + self.conversation_history

        try:
            if stream:
                print("\nAssistant: ", end="", flush=True)
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    stream=True
                )

                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end="", flush=True)
                        full_response += content
                
                print("\n")  # New line after streaming completes
                
                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })
                
                return full_response
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7
                )

                assistant_message = response.choices[0].message.content
                
                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                print(f"\nAssistant: {assistant_message}\n")
                
                return assistant_message

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"\n{error_msg}\n")
            return error_msg

    def handle_command(self, command: str) -> bool:
        command = command.lower().strip()

        if command == "/exit":
            print("\nGoodbye! Thanks for chatting.\n")
            return False

        elif command == "/clear":
            self.conversation_history = []
            self.clear_screen()
            self.print_header()
            print("Conversation history cleared.\n")

        elif command == "/history":
            print("\n" + "=" * 70)
            print("CONVERSATION HISTORY")
            print("=" * 70)
            if not self.conversation_history:
                print("No conversation history yet.\n")
            else:
                for i, msg in enumerate(self.conversation_history, 1):
                    role = msg["role"].upper()
                    content = msg["content"]
                    print(f"\n[{i}] {role}:")
                    print(f"{content}")
                    print("-" * 70)
            print()

        elif command == "/system":
            print("\nCurrent system prompt:")
            print(f"  {self.system_prompt}")
            print("\nEnter new system prompt (or press Enter to keep current):")
            new_prompt = input("> ").strip()
            if new_prompt:
                self.system_prompt = new_prompt
                print(f"\nSystem prompt updated to: {self.system_prompt}\n")
            else:
                print("\nSystem prompt unchanged.\n")

        elif command == "/model":
            print(f"\nCurrent model: {self.model}")
            print("\nAvailable models:")
            print("  1. gpt-4o-mini (fast, cost-effective)")
            print("  2. gpt-4o (most capable)")
            print("  3. gpt-3.5-turbo (fast, legacy)")
            print("\nEnter model number or name (or press Enter to keep current):")
            choice = input("> ").strip()
            
            model_map = {
                "1": "gpt-4o-mini",
                "2": "gpt-4o",
                "3": "gpt-3.5-turbo",
            }
            
            if choice in model_map:
                self.model = model_map[choice]
                print(f"\nModel changed to: {self.model}\n")
            elif choice in ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo", "gpt-4"]:
                self.model = choice
                print(f"\nModel changed to: {self.model}\n")
            elif choice:
                print(f"\nInvalid choice. Model unchanged.\n")
            else:
                print(f"\nModel unchanged.\n")

        else:
            print(f"\nUnknown command: {command}")
            print("Type /exit to see available commands.\n")

        return True

    def run(self):
        """Main application loop"""
        self.clear_screen()
        self.print_header()

        print("Welcome! Start chatting with ChatGPT.\n")
        print("Type your message and press Enter. Use /exit to quit.\n")

        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                # Check if it's a command
                if user_input.startswith("/"):
                    should_continue = self.handle_command(user_input)
                    if not should_continue:
                        break
                    continue

                # Send message to ChatGPT
                self.send_message(user_input, stream=True)

            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Type /exit to quit properly.\n")
                continue
            except EOFError:
                print("\n\nGoodbye!\n")
                break
            except Exception as e:
                print(f"\n\nUnexpected error: {e}\n")
                continue


def main():
    """Entry point for the application"""
    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please set it in your .env file or export it:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        return

    # Create and run the chat terminal
    chat = ChatGPTTerminal()
    chat.run()


if __name__ == "__main__":
    main()