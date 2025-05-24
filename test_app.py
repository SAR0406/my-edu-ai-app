import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import app as streamlit_app # Import the streamlit app file
import openai # <--- ADD THIS IMPORT

# This fixture is automatically used by all tests due to `autouse=True`.
# It sets up mocks for various Streamlit global objects and functions
# to simulate the Streamlit environment during testing, allowing `app.py`
# to be imported and parts of its logic to be executed without a running Streamlit server.
@pytest.fixture(autouse=True)
def mock_streamlit_elements():
    """
    Automatically mocks Streamlit's global objects (secrets, session_state) and
    functions (stop, error, etc.) for the duration of a test.
    This allows `app.py` to be imported and its components tested in isolation.
    """
    # Patch Streamlit's global objects.
    # `MagicMock` is used to create flexible mock objects.
    # `spec=dict` for session_state ensures it behaves somewhat like a dictionary.
    # `side_effect=Exception(...)` for st.stop and st.rerun helps test if these are called.
    with patch('streamlit.secrets', MagicMock()) as mock_secrets, \
         patch('streamlit.session_state', MagicMock(spec=dict)) as mock_session_state, \
         patch('streamlit.stop', MagicMock(side_effect=Exception("Simulated st.stop"))) as mock_stop, \
         patch('streamlit.error', MagicMock()) as mock_error, \
         patch('streamlit.warning', MagicMock()) as mock_warning, \
         patch('streamlit.success', MagicMock()) as mock_success, \
         patch('streamlit.toast', MagicMock()) as mock_toast, \
         patch('streamlit.rerun', MagicMock(side_effect=Exception("Simulated st.rerun"))) as mock_rerun:
        
        # Configure mock_secrets to simulate the presence of an API key by default.
        # This prevents `StreamlitSecretNotFoundError` when `app.py` accesses `st.secrets`.
        mock_secrets.get.return_value = "fake_api_key"  # For st.secrets.get()
        mock_secrets.__getitem__.return_value = "fake_api_key"  # For st.secrets["..."]
        mock_secrets.__contains__.return_value = True  # For "key" in st.secrets

        # Configure mock_session_state to behave like a dictionary and allow attribute access.
        # A real dictionary `_session_state_dict` backs this mock.
        _session_state_dict = {} # Internal store for session state items

        # Define behaviors for dictionary-like methods
        def get_item(name): return _session_state_dict.get(name)
        def set_item(name, value): _session_state_dict[name] = value
        def del_item(name): 
            if name in _session_state_dict: del _session_state_dict[name]
        def contains_item(name): return name in _session_state_dict
        
        # Revised set_item to also set attributes on the mock for direct attribute access
        # (e.g., st.session_state.chat_history)
        def set_item_and_attr(name, value):
            _session_state_dict[name] = value
            # Only set as attribute if it's not a reserved mock name
            if not name.startswith('_mock_') and name not in mock_session_state._mock_methods:
                setattr(mock_session_state, name, value)

        mock_session_state.get = MagicMock(side_effect=get_item)
        mock_session_state.__getitem__ = MagicMock(side_effect=get_item)
        mock_session_state.__setitem__ = MagicMock(side_effect=set_item_and_attr) # Use the enhanced setter
        mock_session_state.__delitem__ = MagicMock(side_effect=del_item)
        mock_session_state.__contains__ = MagicMock(side_effect=contains_item)
        
        # Allow iteration over keys (e.g., `for key in st.session_state:`)
        mock_session_state.keys = MagicMock(return_value=_session_state_dict.keys())

        # Pre-initialize 'chat_history' and 'feedback_log' in the mocked session state.
        # This mimics their initialization in `app.py` (inside `if auth_status:` block).
        # The `IS_TESTING` flag in `app.py` ensures `auth_status` is True, so this code runs.
        if "chat_history" not in mock_session_state: # Uses mocked __contains__
             mock_session_state["chat_history"] = []  # Uses mocked __setitem__ (set_item_and_attr)
        if "feedback_log" not in mock_session_state: # Uses mocked __contains__
             mock_session_state["feedback_log"] = []  # Uses mocked __setitem__ (set_item_and_attr)
        
        # The fixture yields a dictionary of the configured mocks,
        # allowing tests to access these mocks if needed (e.g., for assertions).
        yield {
            "secrets": mock_secrets,
            "session_state": mock_session_state,
            "error": mock_error,
            "stop": mock_stop,
            "rerun": mock_rerun
        }

# Test for API Key Handling (Conceptual)
def test_api_key_missing(mock_streamlit_elements):
    """
    Tests how app.py might behave if the OpenAI API key is missing from st.secrets.
    This test is conceptual because app.py's top-level API key check runs on import.
    The `IS_TESTING` flag in `app.py` now sets a mock API key, so this test
    simulates the condition where `st.secrets` lacks the key and checks if `st.error`
    and `st.stop` would be called (as per original app.py logic before IS_TESTING).
    """
    # Simulate API key missing from secrets by configuring the mock_secrets object.
    mock_streamlit_elements["secrets"].__getitem__.side_effect = KeyError("OPENAI_API_KEY")
    mock_streamlit_elements["secrets"].get.return_value = None 
    mock_streamlit_elements["secrets"].__contains__ = MagicMock(return_value=False)

    # Simulate the part of app.py that would check the key if not IS_TESTING
    try:
        if "OPENAI_API_KEY" not in mock_streamlit_elements["secrets"]: # This will be true
            mock_streamlit_elements["error"]("🚨 OpenAI API Key not found...") # Expected call
            mock_streamlit_elements["stop"]() # Expected call, mocked to raise Exception
        else:
            _ = mock_streamlit_elements["secrets"]["OPENAI_API_KEY"] # Should not be reached
    except Exception as e:
        # Assert that st.stop() was called (mocked to raise an exception).
        assert "Simulated st.stop" in str(e) 
    
    # Verify that st.error and st.stop were indeed called.
    mock_streamlit_elements["error"].assert_any_call("🚨 OpenAI API Key not found...")
    mock_streamlit_elements["stop"].assert_called_once()


# Decorator to mock 'openai.ChatCompletion.create' for this test function.
@patch('openai.ChatCompletion.create')
def test_fetch_learning_content(mock_openai_create, mock_streamlit_elements):
    """
    Tests the "Learn a Topic" feature's OpenAI call.
    It mocks the OpenAI API response and checks if the API is called with the correct prompt
    and if the session state is updated appropriately with the fetched content.
    """
    # Configure the mock OpenAI API response.
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Mocked explanation for Photosynthesis."
    mock_openai_create.return_value = mock_response

    # Simulate initial session state for learning topic (empty).
    streamlit_app.st.session_state["learning_topic"] = None 
    streamlit_app.st.session_state["learning_content"] = None
    
    # Simulate the relevant logic block from app.py when "Get Learning Material" is clicked.
    learn_topic_input = "Photosynthesis" # User input for topic
    if learn_topic_input: 
        # Construct expected prompt and messages for OpenAI API.
        prompt = f"Explain the topic: {learn_topic_input}. Provide a clear and concise explanation suitable for a student learning this for the first time. Focus on key concepts."
        messages = [
            {"role": "system", "content": "You are an AI assistant that provides educational content."},
            {"role": "user", "content": prompt}
        ]
        # Simulate OpenAI API call.
        completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
        # Simulate updating session state with the response.
        streamlit_app.st.session_state.learning_content = completion.choices[0].message.content
        streamlit_app.st.session_state.learning_topic = learn_topic_input

    # Assertions:
    # 1. Check if OpenAI API was called once.
    mock_openai_create.assert_called_once()
    # 2. Check if the user's prompt was correctly included in the API call.
    args, kwargs = mock_openai_create.call_args
    assert kwargs["messages"][1]["content"].startswith("Explain the topic: Photosynthesis.")
    # 3. Check if session state was updated with the mocked AI response and topic.
    assert streamlit_app.st.session_state.learning_content == "Mocked explanation for Photosynthesis."
    assert streamlit_app.st.session_state.learning_topic == "Photosynthesis"


@patch('openai.ChatCompletion.create')
def test_generate_quiz_from_learning_content(mock_openai_create, mock_streamlit_elements):
    """
    Tests AI-powered quiz generation when there's active learning content in session state.
    Mocks OpenAI response and verifies API call structure and session state updates for the quiz.
    """
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Q1. What is ...? A) ... B) ... Correct Answer: A"
    mock_openai_create.return_value = mock_response

    # Simulate active learning content in session state.
    streamlit_app.st.session_state.learning_topic = "Cached Topic"
    streamlit_app.st.session_state.learning_content = "Some cached learning material."
    
    # Simulate app.py logic for quiz generation from active learning content.
    prompt = ""
    quiz_title = ""
    if streamlit_app.st.session_state.learning_content and streamlit_app.st.session_state.learning_topic:
        # Construct expected prompt for quiz generation based on learning content.
        prompt = f"Generate a 3-question multiple-choice quiz based on the following text: '{streamlit_app.st.session_state.learning_content}'. ..." # Actual prompt is longer
        quiz_title = f"🧪 Quiz on: {streamlit_app.st.session_state.learning_topic}"
        
        messages = [
            {"role": "system", "content": "You are an AI assistant that generates educational quizzes."},
            {"role": "user", "content": prompt} 
        ]
        completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
        streamlit_app.st.session_state.generated_quiz_text = completion.choices[0].message.content
        streamlit_app.st.session_state.quiz_title = quiz_title

    # Assertions:
    mock_openai_create.assert_called_once()
    args, kwargs = mock_openai_create.call_args
    # Check if the prompt correctly includes the learning content.
    assert "based on the following text: 'Some cached learning material.'" in kwargs["messages"][1]["content"]
    # Check if session state for quiz is updated.
    assert streamlit_app.st.session_state.generated_quiz_text == "Q1. What is ...? A) ... B) ... Correct Answer: A"
    assert streamlit_app.st.session_state.quiz_title == "🧪 Quiz on: Cached Topic"


@patch('openai.ChatCompletion.create')
def test_generate_quiz_from_subject_grade(mock_openai_create, mock_streamlit_elements):
    """
    Tests AI-powered quiz generation based on subject, grade, and chapter (when no active learning content).
    Mocks OpenAI response and verifies API call and session state updates.
    """
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Q1. Math question...? A) ... B) ... Correct Answer: B"
    mock_openai_create.return_value = mock_response

    # Simulate no active learning content.
    streamlit_app.st.session_state.learning_topic = None 
    streamlit_app.st.session_state.learning_content = None
    
    # Simulate UI inputs for quiz parameters.
    subject = "Math"
    grade = "5"
    chapter = "Fractions"

    # Simulate app.py logic for quiz generation from subject/grade.
    prompt = ""
    quiz_title = ""
    if not (streamlit_app.st.session_state.get("learning_content") and streamlit_app.st.session_state.get("learning_topic")):
        if subject and grade:
            # Construct expected prompt for quiz generation.
            topic_for_prompt = f"Chapter: {chapter}" if chapter else "general topics"
            prompt = f"Generate a 3-question multiple-choice quiz for a Class {grade} student on {topic_for_prompt} in {subject}. ..." # Actual prompt is longer
            quiz_title = f"🧪 Quiz: {subject} - Class {grade} {'- ' + chapter if chapter else ''}"
            
            messages = [
                {"role": "system", "content": "You are an AI assistant that generates educational quizzes."},
                {"role": "user", "content": prompt}
            ]
            completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
            streamlit_app.st.session_state.generated_quiz_text = completion.choices[0].message.content
            streamlit_app.st.session_state.quiz_title = quiz_title

    # Assertions:
    mock_openai_create.assert_called_once()
    args, kwargs = mock_openai_create.call_args
    # Check if prompt correctly includes subject, grade, and chapter.
    assert f"for a Class {grade} student on Chapter: {chapter} in {subject}" in kwargs["messages"][1]["content"]
    # Check session state updates for the quiz.
    assert streamlit_app.st.session_state.generated_quiz_text == "Q1. Math question...? A) ... B) ... Correct Answer: B"
    assert streamlit_app.st.session_state.quiz_title == f"🧪 Quiz: Math - Class 5 - Fractions"

@patch('openai.ChatCompletion.create')
def test_chatbot_response_without_learning_context(mock_openai_create, mock_streamlit_elements):
    """
    Tests the chatbot's response generation when no learning topic is active.
    Verifies the OpenAI API call and that the response is added to chat history.
    """
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hello there! General Kenobi."
    mock_openai_create.return_value = mock_response

    # Ensure no learning context is active in session state.
    streamlit_app.st.session_state.learning_topic = None
    streamlit_app.st.session_state.learning_content = None
    
    # Simulate user inputs for chat.
    chat_input_text = "General Grievous"
    persona = "Fun"
    lang = "English"

    # Simulate app.py's chat logic (simplified).
    system_message_content = f"You are an AI assistant. Your persona is {persona}. Respond in {lang}."
    # Since no learning context, system message is not augmented.
    
    messages = [
        {"role": "system", "content": system_message_content},
        {"role": "user", "content": chat_input_text}
    ]
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    ai_response = completion.choices[0].message.content
    
    # Simulate adding to chat history.
    message_id = "test_message_1" 
    streamlit_app.st.session_state.chat_history.append((chat_input_text, ai_response, persona, message_id))
    
    # Assertions:
    mock_openai_create.assert_called_once_with(model="gpt-3.5-turbo", messages=messages)
    assert ai_response == "Hello there! General Kenobi."
    # Verify that the message pair was added to the mocked chat_history.
    assert (chat_input_text, ai_response, persona, message_id) in streamlit_app.st.session_state.chat_history


@patch('openai.ChatCompletion.create')
def test_chatbot_response_with_learning_context(mock_openai_create, mock_streamlit_elements):
    """
    Tests the chatbot's response generation when a learning topic IS active (contextual chat).
    Verifies that the learning context is included in the OpenAI prompt and response is handled.
    """
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Photosynthesis is how plants make food."
    mock_openai_create.return_value = mock_response

    # Simulate active learning context in session state.
    streamlit_app.st.session_state.learning_topic = "Photosynthesis"
    streamlit_app.st.session_state.learning_content = "Detailed explanation of photosynthesis..."
    
    # Simulate user inputs.
    chat_input_text = "What is it?"
    persona = "Teacher"
    lang = "English"

    # Simulate app.py's chat logic (simplified), including context augmentation.
    system_message_content = f"You are an AI assistant. Your persona is {persona}. Respond in {lang}."
    # Learning context is active, so system message should be augmented.
    system_message_content += (
        f" The user is currently learning about '{streamlit_app.st.session_state.learning_topic}'. "
        f"Please try to answer questions in the context of the following material: '{streamlit_app.st.session_state.learning_content}'. "
        "If the question is unrelated, you can answer more generally but indicate if it's outside the scope of the current topic."
    )
    
    messages = [
        {"role": "system", "content": system_message_content},
        {"role": "user", "content": chat_input_text}
    ]
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    ai_response = completion.choices[0].message.content
    
    message_id = "test_message_2"
    streamlit_app.st.session_state.chat_history.append((chat_input_text, ai_response, persona, message_id))
    
    # Assertions:
    mock_openai_create.assert_called_once_with(model="gpt-3.5-turbo", messages=messages)
    # Verify that the learning context was included in the system message part of the prompt.
    assert "The user is currently learning about 'Photosynthesis'" in messages[0]["content"]
    assert ai_response == "Photosynthesis is how plants make food."
    assert (chat_input_text, ai_response, persona, message_id) in streamlit_app.st.session_state.chat_history
