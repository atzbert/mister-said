import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import openai_helper
from openai_helper import transcribe_audio
from openai import OpenAIError
import os
import tempfile

@pytest.mark.asyncio
async def test_transcribe_audio_success():
    """Test successful audio transcription."""
    mock_audio_data = b"fake_ogg_data"
    expected_text = "This is a test transcription."

    # Mock tempfile.NamedTemporaryFile
    mock_ogg_temp_file = MagicMock()
    mock_ogg_temp_file.name = "temp.ogg"
    mock_mp3_temp_file = MagicMock()
    mock_mp3_temp_file.name = "temp.mp3"

    # Mock openai.Audio.transcribe
    mock_transcribe_response = {'text': expected_text}
    
    # Mock convert_ogg_to_mp3
    mock_convert_ogg_to_mp3 = MagicMock()

    with patch('tempfile.NamedTemporaryFile') as mock_named_temp_file, \
         patch('openai.Audio.transcribe', new_callable=AsyncMock) as mock_transcribe, \
         patch('openai_helper.convert_ogg_to_mp3', mock_convert_ogg_to_mp3), \
         patch('os.remove') as mock_os_remove:

        # Configure NamedTemporaryFile to return different mocks for ogg and mp3
        mock_named_temp_file.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_ogg_temp_file)), # for ogg
            MagicMock(__enter__=MagicMock(return_value=mock_mp3_temp_file))  # for mp3
        ]
        mock_transcribe.return_value = mock_transcribe_response

        result = await transcribe_audio(mock_audio_data)

        assert result == expected_text
        
        # Check if NamedTemporaryFile was called for ogg and mp3
        assert mock_named_temp_file.call_count == 2
        mock_named_temp_file.assert_any_call(suffix=".ogg", delete=False)
        mock_named_temp_file.assert_any_call(suffix=".mp3", delete=False)

        # Check if convert_ogg_to_mp3 was called
        mock_convert_ogg_to_mp3.assert_called_once_with(mock_ogg_temp_file.name, mock_mp3_temp_file.name)
        
        # Check if transcribe was called with the mp3 file
        # We need to check the name of the file object passed to transcribe
        assert mock_transcribe.call_args[0][1].name == mock_mp3_temp_file.name

        # Check if os.remove was called for cleanup
        assert mock_os_remove.call_count == 2
        mock_os_remove.assert_any_call(mock_ogg_temp_file.name)
        mock_os_remove.assert_any_call(mock_mp3_temp_file.name)


@pytest.mark.asyncio
async def test_transcribe_audio_openai_error():
    """Test error handling when OpenAI API fails."""
    mock_audio_data = b"fake_ogg_data"

    mock_ogg_temp_file = MagicMock()
    mock_ogg_temp_file.name = "temp.ogg"
    mock_mp3_temp_file = MagicMock()
    mock_mp3_temp_file.name = "temp.mp3"
    
    mock_convert_ogg_to_mp3 = MagicMock()

    with patch('tempfile.NamedTemporaryFile') as mock_named_temp_file, \
         patch('openai.Audio.transcribe', new_callable=AsyncMock) as mock_transcribe, \
         patch('openai_helper.convert_ogg_to_mp3', mock_convert_ogg_to_mp3), \
         patch('os.remove') as mock_os_remove:

        mock_named_temp_file.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_ogg_temp_file)),
            MagicMock(__enter__=MagicMock(return_value=mock_mp3_temp_file))
        ]
        mock_transcribe.side_effect = OpenAIError("OpenAI API error")

        result = await transcribe_audio(mock_audio_data)

        assert result is None
        
        # Ensure cleanup is still attempted
        assert mock_os_remove.call_count == 2
        mock_os_remove.assert_any_call(mock_ogg_temp_file.name)
        mock_os_remove.assert_any_call(mock_mp3_temp_file.name)


@pytest.mark.asyncio
async def test_transcribe_audio_conversion_error():
    """Test error handling when audio conversion fails."""
    mock_audio_data = b"fake_ogg_data"

    mock_ogg_temp_file = MagicMock()
    mock_ogg_temp_file.name = "temp.ogg"
    
    # convert_ogg_to_mp3 will be mocked to raise an exception
    mock_convert_ogg_to_mp3 = MagicMock(side_effect=Exception("Conversion failed"))

    with patch('tempfile.NamedTemporaryFile') as mock_named_temp_file, \
         patch('openai_helper.convert_ogg_to_mp3', mock_convert_ogg_to_mp3), \
         patch('os.remove') as mock_os_remove:
        
        # Only the ogg file should be created
        mock_named_temp_file.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_ogg_temp_file))
        ]

        result = await transcribe_audio(mock_audio_data)

        assert result is None
        
        # Ensure ogg file cleanup is attempted
        # mp3 file won't be created or cleaned up if conversion fails early
        mock_os_remove.assert_called_once_with(mock_ogg_temp_file.name)
        # Check that the mp3 file (which shouldn't be named if conversion fails before its tempfile creation)
        # is not attempted to be removed. The second NamedTemporaryFile call for mp3 won't happen.
        assert mock_named_temp_file.call_count == 1 # Only for ogg

@pytest.mark.asyncio
async def test_transcribe_audio_unexpected_response_format():
    """Test handling of unexpected response format from OpenAI."""
    mock_audio_data = b"fake_ogg_data"

    mock_ogg_temp_file = MagicMock()
    mock_ogg_temp_file.name = "temp.ogg"
    mock_mp3_temp_file = MagicMock()
    mock_mp3_temp_file.name = "temp.mp3"
    
    mock_convert_ogg_to_mp3 = MagicMock()
    # Simulate a response that is not None but doesn't contain 'text'
    mock_transcribe_response = {'alternative_text': 'something else'} 

    with patch('tempfile.NamedTemporaryFile') as mock_named_temp_file, \
         patch('openai.Audio.transcribe', new_callable=AsyncMock) as mock_transcribe, \
         patch('openai_helper.convert_ogg_to_mp3', mock_convert_ogg_to_mp3), \
         patch('os.remove') as mock_os_remove:

        mock_named_temp_file.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_ogg_temp_file)),
            MagicMock(__enter__=MagicMock(return_value=mock_mp3_temp_file))
        ]
        mock_transcribe.return_value = mock_transcribe_response

        result = await transcribe_audio(mock_audio_data)

        assert result is None
        
        # Ensure cleanup is still attempted
        assert mock_os_remove.call_count == 2
        mock_os_remove.assert_any_call(mock_ogg_temp_file.name)
        mock_os_remove.assert_any_call(mock_mp3_temp_file.name)

@pytest.mark.asyncio
async def test_transcribe_audio_empty_audio_data():
    """Test with empty audio data."""
    mock_audio_data = b"" # Empty audio data
    
    # We expect it to try to write this empty data and proceed
    # The conversion or transcription might fail, or produce empty result
    # Depending on how convert_ogg_to_mp3 and openai.Audio.transcribe handle empty files

    mock_ogg_temp_file = MagicMock()
    mock_ogg_temp_file.name = "temp_empty.ogg"
    mock_mp3_temp_file = MagicMock()
    mock_mp3_temp_file.name = "temp_empty.mp3"
    
    mock_convert_ogg_to_mp3 = MagicMock()
    # Let's assume transcription of an empty/invalid audio results in None or empty text
    mock_transcribe_response = {'text': ''} 

    with patch('tempfile.NamedTemporaryFile') as mock_named_temp_file, \
         patch('openai.Audio.transcribe', new_callable=AsyncMock) as mock_transcribe, \
         patch('openai_helper.convert_ogg_to_mp3', mock_convert_ogg_to_mp3), \
         patch('os.remove') as mock_os_remove:

        mock_named_temp_file.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_ogg_temp_file)),
            MagicMock(__enter__=MagicMock(return_value=mock_mp3_temp_file))
        ]
        mock_transcribe.return_value = mock_transcribe_response

        result = await transcribe_audio(mock_audio_data)

        assert result == "" # Expecting empty string if transcription of empty audio is empty
        
        assert mock_os_remove.call_count == 2
        mock_os_remove.assert_any_call(mock_ogg_temp_file.name)
        mock_os_remove.assert_any_call(mock_mp3_temp_file.name)

        # Verify that the empty data was "written"
        # The actual write happens on the real file object returned by mock_ogg_temp_file.__enter__()
        # So, we check the write call on that specific mock.
        mock_ogg_temp_file.write.assert_called_once_with(mock_audio_data)
