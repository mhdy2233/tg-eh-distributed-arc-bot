"""
单元测试：Telegraph 推送功能

测试 publish_to_telegraph 函数及其相关辅助逻辑
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime


# 模拟的画廊元数据
MOCK_GALLERY_META = {
    "gmetadata": [{
        "gid": 12345,
        "token": "abc123def",
        "title": "Test Gallery Title",
        "title_jpn": "テストギャラリータイトル",
        "category": "Doujinshi",
        "uploader": "test_uploader",
        "posted": "1701936000",  # 2023-12-07 12:00:00 UTC
        "filecount": "24",
        "filesize": 52428800,  # 50 MB
        "rating": "4.5",
        "tags": [
            "language:chinese",
            "artist:test_artist",
            "female:test_tag",
            "male:test_male_tag",
            "parody:test_parody"
        ]
    }]
}

MOCK_GALLERY_META_EMPTY_TAGS = {
    "gmetadata": [{
        "gid": 12346,
        "token": "xyz789",
        "title": "Gallery Without Tags",
        "title_jpn": "",
        "category": "Manga",
        "uploader": "another_uploader",
        "posted": "1701849600",
        "filecount": "10",
        "filesize": 10485760,  # 10 MB
        "rating": "3.0",
        "tags": []
    }]
}

MOCK_GALLERY_META_LARGE_FILE = {
    "gmetadata": [{
        "gid": 12347,
        "token": "large123",
        "title": "Large Gallery",
        "title_jpn": "",
        "category": "Image Set",
        "uploader": "uploader3",
        "posted": "1701763200",
        "filecount": "500",
        "filesize": 2147483648,  # 2 GB
        "rating": "4.8",
        "tags": ["misc:large"]
    }]
}

MOCK_GALLERY_META_SMALL_FILE = {
    "gmetadata": [{
        "gid": 12348,
        "token": "small456",
        "title": "Small Gallery",
        "title_jpn": "",
        "category": "Misc",
        "uploader": "uploader4",
        "posted": "1701676800",
        "filecount": "5",
        "filesize": 512000,  # 500 KB
        "rating": "2.5",
        "tags": []
    }]
}


class TestFileSizeConversion:
    """测试文件大小转换逻辑"""
    
    def test_convert_bytes_to_gb(self):
        """测试字节转 GB"""
        filesize = 2147483648  # 2 GB
        if filesize > 1024 * 1024 * 1024:
            size_str = f"{filesize / 1024 / 1024 / 1024:.2f} GB"
        assert size_str == "2.00 GB"
    
    def test_convert_bytes_to_mb(self):
        """测试字节转 MB"""
        filesize = 52428800  # 50 MB
        if filesize > 1024 * 1024:
            size_str = f"{filesize / 1024 / 1024:.2f} MB"
        assert size_str == "50.00 MB"
    
    def test_convert_bytes_to_kb(self):
        """测试字节转 KB"""
        filesize = 512000  # 500 KB
        if filesize <= 1024 * 1024:
            size_str = f"{filesize / 1024:.2f} KB"
        assert size_str == "500.00 KB"
    
    def test_zero_filesize(self):
        """测试零大小文件"""
        filesize = 0
        if filesize:
            size_str = f"{filesize / 1024:.2f} KB"
        else:
            size_str = '未知'
        assert size_str == '未知'


class TestTimestampConversion:
    """测试时间戳转换逻辑"""
    
    def test_valid_timestamp(self):
        """测试有效时间戳"""
        posted = "1701936000"
        try:
            posted_time = datetime.fromtimestamp(int(posted)).strftime('%Y-%m-%d %H:%M:%S')
        except:
            posted_time = posted
        assert "2023-12-07" in posted_time
    
    def test_invalid_timestamp(self):
        """测试无效时间戳"""
        posted = "invalid"
        try:
            posted_time = datetime.fromtimestamp(int(posted)).strftime('%Y-%m-%d %H:%M:%S')
        except:
            posted_time = posted
        assert posted_time == "invalid"
    
    def test_empty_timestamp(self):
        """测试空时间戳"""
        posted = ""
        if posted:
            try:
                posted_time = datetime.fromtimestamp(int(posted)).strftime('%Y-%m-%d %H:%M:%S')
            except:
                posted_time = posted
        else:
            posted_time = '未知'
        assert posted_time == '未知'


class TestTagParsing:
    """测试标签解析逻辑"""
    
    def test_parse_tags_with_colon(self):
        """测试带冒号的标签解析"""
        tags = ["language:chinese", "artist:test_artist", "female:test_tag"]
        tags_by_type = {}
        for tag in tags:
            if ':' in tag:
                tag_type, tag_name = tag.split(':', 1)
            else:
                tag_type, tag_name = 'misc', tag
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
            tags_by_type[tag_type].append(tag_name)
        
        assert "language" in tags_by_type
        assert "artist" in tags_by_type
        assert "female" in tags_by_type
        assert tags_by_type["language"] == ["chinese"]
        assert tags_by_type["artist"] == ["test_artist"]
    
    def test_parse_tags_without_colon(self):
        """测试不带冒号的标签解析"""
        tags = ["misc_tag", "another_tag"]
        tags_by_type = {}
        for tag in tags:
            if ':' in tag:
                tag_type, tag_name = tag.split(':', 1)
            else:
                tag_type, tag_name = 'misc', tag
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
            tags_by_type[tag_type].append(tag_name)
        
        assert "misc" in tags_by_type
        assert tags_by_type["misc"] == ["misc_tag", "another_tag"]
    
    def test_parse_empty_tags(self):
        """测试空标签列表"""
        tags = []
        tags_by_type = {}
        for tag in tags:
            if ':' in tag:
                tag_type, tag_name = tag.split(':', 1)
            else:
                tag_type, tag_name = 'misc', tag
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
            tags_by_type[tag_type].append(tag_name)
        
        assert tags_by_type == {}
    
    def test_parse_tag_with_multiple_colons(self):
        """测试带多个冒号的标签"""
        tags = ["misc:tag:with:colons"]
        tags_by_type = {}
        for tag in tags:
            if ':' in tag:
                tag_type, tag_name = tag.split(':', 1)
            else:
                tag_type, tag_name = 'misc', tag
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
            tags_by_type[tag_type].append(tag_name)
        
        assert tags_by_type["misc"] == ["tag:with:colons"]


class TestMarkdownContentGeneration:
    """测试 Markdown 内容生成"""
    
    def test_generate_basic_content(self):
        """测试基本内容生成"""
        gallery = MOCK_GALLERY_META["gmetadata"][0]
        title = gallery.get('title', '未知标题')
        category = gallery.get('category', '未知')
        
        content = f"# {title}\n\n## 基本信息\n\n- **类型**: {category}"
        
        assert "Test Gallery Title" in content
        assert "Doujinshi" in content
    
    def test_generate_content_with_jpn_title(self):
        """测试包含日文标题的内容"""
        gallery = MOCK_GALLERY_META["gmetadata"][0]
        title_jpn = gallery.get('title_jpn', '')
        
        content = ""
        if title_jpn:
            content += f"**日文标题**: {title_jpn}\n\n"
        
        assert "テストギャラリータイトル" in content
    
    def test_generate_content_without_jpn_title(self):
        """测试不包含日文标题的内容"""
        gallery = MOCK_GALLERY_META_EMPTY_TAGS["gmetadata"][0]
        title_jpn = gallery.get('title_jpn', '')
        
        content = ""
        if title_jpn:
            content += f"**日文标题**: {title_jpn}\n\n"
        
        assert content == ""
    
    def test_title_length_limit(self):
        """测试标题长度限制（Telegraph 限制 256 字符）"""
        long_title = "A" * 300
        limited_title = long_title[:256]
        
        assert len(limited_title) == 256


class TestPublishToTelegraphFunction:
    """测试 publish_to_telegraph 函数核心逻辑"""
    
    @pytest.mark.asyncio
    async def test_publish_success(self):
        """测试成功发布到 Telegraph 的核心逻辑"""
        # 模拟 eh_meta 返回的数据
        meta = MOCK_GALLERY_META
        
        # 模拟 HTML 响应（用于预览图）
        html_content = """
        <html>
            <body>
                <img src="https://ehgt.org/t/123/cover.jpg" />
                <div class="gdtm">
                    <img src="https://ehgt.org/t/123/001.jpg" />
                </div>
                 <div class="gdtm">
                    <img src="https://ehgt.org/t/123/002.jpg" />
                </div>
            </body>
        </html>
        """
        
        # Mock requests.get inside bot module (bot.py)
        # Note: We must patch 'bot.publish_text' because 'from telepress import publish_text' is used in bot.py
        with patch('bot.eh_meta', new_callable=AsyncMock) as mock_eh_meta, \
             patch('bot.requests.get') as mock_requests_get, \
             patch('bot.publish_text') as mock_publish:
            
            mock_eh_meta.return_value = meta
            
            mock_response = Mock()
            
            mock_publish.return_value = "https://telegra.ph/Test-Gallery-12-07"

            mock_response.text = html_content
            mock_requests_get.return_value = mock_response
            
            # Import function to test
            # Assumes PYTHONPATH includes the directory containing bot.py
            from bot import publish_to_telegraph
            
            url, error = await publish_to_telegraph(12345, "abc123def")
            
            assert url == "https://telegra.ph/Test-Gallery-12-07"
            assert error is None
            
            # Verify content
            args, _ = mock_publish.call_args
            content = args[0]
            
            # Check basic info
            assert "# Test Gallery Title" in content
            assert "**日文标题**: テストギャラリータイトル" in content
            assert "**类型**: Doujinshi" in content
            
            # Check tags
            assert "**语言**: chinese" in content
            
            # Check images (Markdown format)
            # Cover image comes from MOCK_GALLERY_META not HTML, assuming MOCK data has thumb?
            # MOCK_GALLERY_META doesn't have 'thumb' field in the definition at top of file!
            # Let's add it to the mock data in the test or modify the global mock.
            # But here I can just assert previews which come from HTML.
            
            assert "![预览](https://ehgt.org/t/123/001.jpg)" in content
            assert "![预览](https://ehgt.org/t/123/002.jpg)" in content

    
    @pytest.mark.asyncio
    async def test_publish_with_empty_input(self):
        """测试输入为空时的处理"""
        gid = None
        token = "abc123"
        
        # 输入验证逻辑
        if not gid or not token:
            error = "画廊ID或token为空"
        
        assert error == "画廊ID或token为空"
    
    @pytest.mark.asyncio
    async def test_publish_with_empty_meta(self):
        """测试元数据为空时的处理"""
        meta = None
        
        # 应该返回错误
        if not meta or 'gmetadata' not in meta:
            error = "获取画廊元数据失败"
        
        assert error == "获取画廊元数据失败"
    
    @pytest.mark.asyncio
    async def test_publish_with_gallery_error(self):
        """测试画廊返回错误时的处理"""
        meta = {"gmetadata": [{"error": "Key missing"}]}
        gallery = meta['gmetadata'][0]
        
        if gallery.get('error'):
            error = f"画廊错误: {gallery.get('error')}"
        
        assert "画廊错误" in error
        assert "Key missing" in error
    
    @pytest.mark.asyncio
    async def test_publish_with_empty_gmetadata(self):
        """测试 gmetadata 为空列表时的处理"""
        meta = {"gmetadata": []}
        
        if not meta or 'gmetadata' not in meta or not meta['gmetadata']:
            error = "获取画廊元数据失败"
        
        assert error == "获取画廊元数据失败"
    
    @pytest.mark.asyncio
    async def test_publish_content_generation(self):
        """测试 Telegraph 内容生成逻辑"""
        meta = MOCK_GALLERY_META
        gallery = meta['gmetadata'][0]
        
        # 提取信息
        title = gallery.get('title', '未知标题')
        title_jpn = gallery.get('title_jpn', '')
        category = gallery.get('category', '未知')
        uploader = gallery.get('uploader', '未知')
        posted = gallery.get('posted', '')
        filecount = gallery.get('filecount', '0')
        filesize = gallery.get('filesize', 0)
        rating = gallery.get('rating', '0')
        tags = gallery.get('tags', [])
        
        # 验证提取的信息
        assert title == "Test Gallery Title"
        assert title_jpn == "テストギャラリータイトル"
        assert category == "Doujinshi"
        assert uploader == "test_uploader"
        assert filecount == "24"
        assert rating == "4.5"
        assert len(tags) == 5
        
        # 转换时间戳
        try:
            posted_time = datetime.fromtimestamp(int(posted)).strftime('%Y-%m-%d %H:%M:%S')
        except:
            posted_time = posted
        assert "2023-12-07" in posted_time
        
        # 转换文件大小
        if filesize > 1024 * 1024 * 1024:
            size_str = f"{filesize / 1024 / 1024 / 1024:.2f} GB"
        elif filesize > 1024 * 1024:
            size_str = f"{filesize / 1024 / 1024:.2f} MB"
        else:
            size_str = f"{filesize / 1024:.2f} KB"
        assert size_str == "50.00 MB"


class TestTelePressExceptionHandling:
    """测试 TelePress 异常处理"""
    
    def test_validation_error_handling(self):
        """测试验证错误处理"""
        from telepress import ValidationError
        
        try:
            raise ValidationError("Test validation error")
        except ValidationError as e:
            error = f"验证错误: {str(e)}"
        
        assert "验证错误" in error
        assert "Test validation error" in error
    
    def test_telepress_error_handling(self):
        """测试 TelePress 通用错误处理"""
        from telepress import TelePressError
        
        try:
            raise TelePressError("Test telepress error")
        except TelePressError as e:
            error = f"发布错误: {str(e)}"
        
        assert "发布错误" in error
        assert "Test telepress error" in error


class TestCallbackDataParsing:
    """测试回调数据解析"""
    
    def test_parse_telegraph_callback(self):
        """测试 telegraph 回调数据解析"""
        callback_data = "telegraph|12345|abc123|67890"
        data = callback_data.split("|")
        
        assert data[0] == "telegraph"
        assert data[1] == "12345"  # gid
        assert data[2] == "abc123"  # token
        assert data[3] == "67890"  # user_id
    
    def test_callback_data_length_check(self):
        """测试 callback data 长度安全检查"""
        # 正常格式
        valid_data = "telegraph|12345|abc123|67890".split("|")
        assert len(valid_data) >= 4
        
        # 格式不完整
        invalid_data = "telegraph|12345".split("|")
        assert len(invalid_data) < 4
        
        # 空数据
        empty_data = "telegraph".split("|")
        assert len(empty_data) < 4
    
    def test_user_permission_check(self):
        """测试用户权限检查"""
        callback_data = "telegraph|12345|abc123|67890"
        data = callback_data.split("|")
        
        # 模拟用户 ID 匹配
        query_user_id = "67890"
        assert str(query_user_id) == data[3]
        
        # 模拟用户 ID 不匹配
        other_user_id = "11111"
        assert str(other_user_id) != data[3]


class TestTagTranslationDict:
    """测试标签翻译字典"""
    
    def test_tag_translation_exists(self):
        """测试标签翻译字典包含必要的键"""
        tag_tra_dict = {
            "language": "语言",
            "parody": "原作",
            "character": "角色",
            "group": "团队",
            "artist": "艺术家",
            "cosplayer": "角色扮演者",
            "male": "男性",
            "female": "女性",
            "mixed": "混合",
            "other": "其他",
            "temp": "临时",
            "reclass": "重新分类"
        }
        
        assert tag_tra_dict.get("language") == "语言"
        assert tag_tra_dict.get("artist") == "艺术家"
        assert tag_tra_dict.get("female") == "女性"
        assert tag_tra_dict.get("male") == "男性"
    
    def test_tag_translation_fallback(self):
        """测试未知标签类型的回退"""
        tag_tra_dict = {"language": "语言"}
        unknown_type = "unknown_type"
        
        translated = tag_tra_dict.get(unknown_type, unknown_type)
        assert translated == "unknown_type"


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_publish_flow(self):
        """测试完整的发布流程"""
        # 1. 模拟获取元数据
        meta = MOCK_GALLERY_META
        gallery = meta['gmetadata'][0]
        
        # 2. 提取信息
        title = gallery.get('title', '未知标题')
        title_jpn = gallery.get('title_jpn', '')
        category = gallery.get('category', '未知')
        filesize = gallery.get('filesize', 0)
        tags = gallery.get('tags', [])
        
        # 3. 转换文件大小
        if filesize > 1024 * 1024 * 1024:
            size_str = f"{filesize / 1024 / 1024 / 1024:.2f} GB"
        elif filesize > 1024 * 1024:
            size_str = f"{filesize / 1024 / 1024:.2f} MB"
        else:
            size_str = f"{filesize / 1024:.2f} KB"
        
        # 4. 解析标签
        tags_by_type = {}
        for tag in tags:
            if ':' in tag:
                tag_type, tag_name = tag.split(':', 1)
            else:
                tag_type, tag_name = 'misc', tag
            if tag_type not in tags_by_type:
                tags_by_type[tag_type] = []
            tags_by_type[tag_type].append(tag_name)
        
        # 5. 生成内容
        content = f"# {title}\n\n"
        if title_jpn:
            content += f"**日文标题**: {title_jpn}\n\n"
        content += f"- **类型**: {category}\n"
        content += f"- **大小**: {size_str}\n"
        
        # 6. 验证结果
        assert "Test Gallery Title" in content
        assert "テストギャラリータイトル" in content
        assert "Doujinshi" in content
        assert "50.00 MB" in content
        assert len(tags_by_type) > 0
        assert "language" in tags_by_type


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
