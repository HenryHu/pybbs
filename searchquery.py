import re
import Post
from Util import Util

class SearchQuery:
    def __init__(self, query_expr):
        self.query_expr = query_expr

    def match(self, board, post_entry):
        return self.match_expr(self.query_expr, board, post_entry)

    def match_expr(self, expr, board, post_entry):
        if expr[0] == 'or':
            for child in expr[1:]:
                child_ret = self.match_expr(child, board, post_entry)
                if child_ret:
                    return True
            return False
        if expr[0] == 'and':
            for child in expr[1:]:
                child_ret = self.match_expr(child, board, post_entry)
                if not child_ret:
                    return False
            return True
        if expr[0] == 'not':
            return not self.match_expr(expr[1], board, post_entry)
        if expr[0] == 'author':
            return re.match(expr[1], Util.gbkDec(post_entry.owner))
        if expr[0] == 'title':
            return re.match(expr[1], Util.gbkDec(post_entry.title))
        if expr[0] == 'content':
            post = Post.Post(board.GetBoardDir(post_entry.filename))
            return re.match(expr[1], post.GetBody())
        if expr[0] == 'm':
            return post_entry.IsMarked()
        if expr[0] == 'g':
            return post_entry.InDigest()
        if expr[0] == 'noreply':
            return post_entry.CannotReply()
        if expr[0] == 'ge' or expr[0] == 'le' or expr[0] == 'eq':
            if expr[1] == 'posttime':
                left = post_entry.GetPostTime()
            elif expr[1] == 'thread':
                left = post_entry.groupid
            elif expr[1] == 'size':
                left = post_entry.eff_size
            right = expr[2]
            if expr[0] == 'ge':
                return left >= right
            if expr[1] == 'le':
                return left <= right
            if expr[1] == 'eq':
                return left == right
        if expr[0] == 'has_attach':
            return (post_entry.attachment != 0)
        return False

