import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach } from "vitest";
import { installRecognition, installSynthesis, removeRecognition, removeSynthesis, voice } from "@/test/fakeSpeech";
import { AudioPlayer } from "./AudioPlayer";
import { MicButton } from "./MicButton";
import { TypeInstead } from "./TypeInstead";
import { VoiceInput } from "./VoiceInput";

afterEach(() => {
  removeRecognition();
  removeSynthesis();
  vi.unstubAllGlobals();
});

describe("TypeInstead", () => {
  test("opens, then sends trimmed text", async () => {
    const onSubmit = vi.fn();
    render(<TypeInstead onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: /type instead/i }));
    const box = screen.getByRole("textbox");
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
    await userEvent.type(box, "  my eye is red  {Enter}");
    expect(onSubmit).toHaveBeenCalledWith("my eye is red");
    expect(box).toHaveValue("");
  });

  test("speaks the patient's language", () => {
    render(<TypeInstead lang="kn" onSubmit={() => {}} />);
    expect(screen.getByRole("button", { name: "ಟೈಪ್ ಮಾಡಿ" })).toBeInTheDocument();
  });
});

describe("MicButton", () => {
  test("shows pressed state while listening", () => {
    const { rerender } = render(<MicButton status="idle" onPress={() => {}} label="Tap and speak" />);
    expect(screen.getByRole("button", { name: "Tap and speak" })).toHaveAttribute("aria-pressed", "false");
    rerender(<MicButton status="listening" onPress={() => {}} label="Tap to stop" />);
    expect(screen.getByRole("button", { name: "Tap to stop" })).toHaveAttribute("aria-pressed", "true");
    rerender(<MicButton status="processing" onPress={() => {}} label="Wait" />);
    expect(screen.getByRole("button", { name: "Wait" })).toBeDisabled();
  });
});

describe("AudioPlayer", () => {
  test("speaks the text in the patient's language and offers replay", async () => {
    const spoken = installSynthesis([voice("kn-IN")]);
    render(<AudioPlayer text="ನಮಸ್ಕಾರ" lang="kn" />);
    await userEvent.click(screen.getByRole("button", { name: "ಕೇಳಿ" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "ಮತ್ತೆ ಕೇಳಿ" })).toBeInTheDocument());
    expect(spoken.map((s) => s.text)).toEqual(["ನಮಸ್ಕಾರ"]);
  });

  test("asks the patient to read when the phone has no voice for the language", async () => {
    installSynthesis([voice("en-US")]);
    render(<AudioPlayer text="வணக்கம்" lang="ta" />);
    await userEvent.click(screen.getByRole("button", { name: "கேளுங்கள்" }));
    expect(await screen.findByRole("status")).toHaveTextContent("தமிழ்");
  });
});

describe("VoiceInput", () => {
  test("without browser speech it says so and opens type-instead", () => {
    removeRecognition();
    render(<VoiceInput lang="en" onText={() => {}} record={false} />);
    expect(screen.getByRole("button", { name: "Tap and speak" })).toBeDisabled();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  test("spoken Kannada reaches the caller", async () => {
    installRecognition([{ kind: "result", text: "kannu kempagide" }]);
    const onText = vi.fn();
    render(<VoiceInput lang="kn" onText={onText} record={false} />);
    await userEvent.click(screen.getByRole("button", { name: "ಒತ್ತಿ ಮಾತನಾಡಿ" }));
    await userEvent.click(await screen.findByRole("button", { name: "ನಿಲ್ಲಿಸಲು ಒತ್ತಿ" }));
    await waitFor(() => expect(onText).toHaveBeenCalled());
    expect(onText.mock.calls[0]?.[0]).toBe("kannu kempagide");
    expect(onText.mock.calls[0]?.[1]).toMatchObject({ typed: false });
  });

  test("hearing nothing asks again in the patient's language and counts failures", async () => {
    installRecognition([{ kind: "error", error: "no-speech" }]);
    const onText = vi.fn();
    const onNotHeard = vi.fn();
    render(<VoiceInput lang="hi" onText={onText} onNotHeard={onNotHeard} record={false} />);
    for (const attempt of [1, 2]) {
      await userEvent.click(screen.getByRole("button", { name: "दबाएँ और बोलें" }));
      await userEvent.click(await screen.findByRole("button", { name: "रोकने के लिए दबाएँ" }));
      await waitFor(() => expect(onNotHeard).toHaveBeenLastCalledWith(attempt));
    }
    expect(screen.getByRole("alert")).toHaveTextContent("सुनाई नहीं दिया");
    expect(onText).not.toHaveBeenCalled();
  });

  test("typed text is marked as typed", async () => {
    removeRecognition();
    const onText = vi.fn();
    render(<VoiceInput lang="en" onText={onText} record={false} />);
    await userEvent.type(screen.getByRole("textbox"), "fever{Enter}");
    expect(onText).toHaveBeenCalledWith("fever", { typed: true });
  });
});
